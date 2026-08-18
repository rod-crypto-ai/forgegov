from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from ...integrations import IntegrationError, upsert_usaspending_award
from ...integration_resilience import quarantine_record
from ...models import Award, AwardSyncRun, ConnectorSource
from ..connectors import connector_registry, get_connector


def seed_connector_registry() -> list[ConnectorSource]:
    rows: list[ConnectorSource] = []
    for connector in connector_registry.values():
        descriptor = connector.descriptor
        row, _ = ConnectorSource.objects.update_or_create(
            key=descriptor.key,
            defaults={
                "name": descriptor.name,
                "scope": descriptor.scope,
                "jurisdiction_code": descriptor.jurisdiction_code,
                "jurisdiction_name": descriptor.jurisdiction_name,
                "official_url": descriptor.official_url,
                "documentation_url": descriptor.documentation_url,
                "license_name": descriptor.license_name,
                "license_url": descriptor.license_url,
                "authentication": descriptor.authentication,
                "capabilities": descriptor.capabilities,
                "rate_limit": descriptor.rate_limit,
            },
        )
        rows.append(row)
    return rows


def connector_registry_payload(probe: bool = False) -> dict[str, Any]:
    seed_connector_registry()
    results: list[dict[str, Any]] = []
    for row in ConnectorSource.objects.all():
        connector = get_connector(row.key)
        health = connector.health() if probe and connector else None
        if health:
            row.last_status = health.get("status", "unknown")
            row.last_checked_at = timezone.now()
            row.last_error = "" if health.get("status") == "healthy" else health.get("detail", "")
            row.save(update_fields=["last_status", "last_checked_at", "last_error", "updated_at"])
        results.append({
            "key": row.key,
            "name": row.name,
            "scope": row.scope,
            "jurisdiction_code": row.jurisdiction_code,
            "jurisdiction_name": row.jurisdiction_name,
            "capabilities": row.capabilities,
            "official_url": row.official_url,
            "documentation_url": row.documentation_url,
            "license_name": row.license_name,
            "license_url": row.license_url,
            "authentication": row.authentication,
            "rate_limit": row.rate_limit,
            "enabled": row.enabled,
            "status": health.get("status") if health else row.last_status,
            "configured": health.get("configured") if health else None,
            "reachable": health.get("reachable") if health else None,
            "detail": health.get("detail") if health else row.last_error,
            "last_checked_at": row.last_checked_at,
            "last_sync_at": row.last_sync_at,
            "record_count": row.record_count,
        })
    return {"connectors": results, "summary": {"total": len(results), "enabled": sum(1 for r in results if r["enabled"]), "healthy": sum(1 for r in results if r["status"] == "healthy")}}


def sync_usaspending_awards(*, start_date: str | None = None, end_date: str | None = None, pages: int = 1, limit: int = 100, keyword: str = "", agency: str = "", naics: str = "") -> AwardSyncRun:
    connector = get_connector("usaspending-awards")
    if connector is None:
        raise IntegrationError("USAspending award connector is not registered.")
    run = AwardSyncRun.objects.create(
        connector_key=connector.descriptor.key,
        status=AwardSyncRun.Status.RUNNING,
        started_at=timezone.now(),
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
    )
    errors: list[str] = []
    created = updated = seen = 0
    try:
        for record in connector.iter_awards(start_date=start_date, end_date=end_date, pages=pages, limit=limit, keyword=keyword, agency=agency, naics=naics):
            seen += 1
            try:
                with transaction.atomic():
                    _, was_created = upsert_usaspending_award(record)
                created += int(was_created)
                updated += int(not was_created)
            except Exception as exc:
                errors.append(str(exc))
                quarantine_record(
                    source="usaspending.gov", record_type="award.usaspending", payload=record,
                    source_id=str(record.get("generated_unique_award_id") or record.get("Award ID") or ""),
                    reason="award_sync_error", error=exc, award_sync_run=run,
                )
        run.status = AwardSyncRun.Status.PARTIAL if errors else AwardSyncRun.Status.SUCCEEDED
    except Exception as exc:
        errors.append(str(exc))
        run.status = AwardSyncRun.Status.FAILED
    run.completed_at = timezone.now()
    run.pages_processed = max(1, pages)
    run.records_seen = seen
    run.records_created = created
    run.records_updated = updated
    run.errors = errors[:100]
    run.save()
    source, _ = ConnectorSource.objects.get_or_create(key=connector.descriptor.key, defaults={"name": connector.descriptor.name})
    source.last_sync_at = run.completed_at
    source.record_count = Award.objects.filter(source="usaspending.gov").count()
    source.last_status = "healthy" if run.status == AwardSyncRun.Status.SUCCEEDED else run.status
    source.last_error = "\n".join(errors[:5])
    source.save()
    return run


def award_intelligence_summary(*, agency: str = "", naics: str = "", psc: str = "", recipient: str = "", limit: int = 10) -> dict[str, Any]:
    from django.db.models import Count, Max, Sum, Q
    qs = Award.objects.filter(jurisdiction_level="federal")
    if agency:
        qs = qs.filter(Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency))
    if naics:
        qs = qs.filter(naics_code=naics)
    if psc:
        qs = qs.filter(psc_code=psc)
    if recipient:
        qs = qs.filter(recipient_name__icontains=recipient)
    grouped = list(qs.exclude(recipient_name="").values("recipient_name", "recipient_uei").annotate(award_count=Count("id"), obligated=Sum("obligated_amount"), potential=Sum("potential_amount"), latest_end=Max("end_date")).order_by("-award_count", "-obligated")[:limit])
    latest = list(qs.order_by("-start_date", "-updated_at").values("source_id", "award_number", "recipient_name", "awarding_agency", "obligated_amount", "potential_amount", "start_date", "end_date", "naics_code", "psc_code")[:limit])
    return {
        "filters": {"agency": agency, "naics": naics, "psc": psc, "recipient": recipient},
        "totals": {"records": qs.count(), "obligated": qs.aggregate(total=Sum("obligated_amount"))["total"] or 0, "potential": qs.aggregate(total=Sum("potential_amount"))["total"] or 0},
        "past_winners": grouped,
        "likely_incumbent": grouped[0] if grouped else None,
        "latest_awards": latest,
        "classification": "official_historical_awards",
        "warning": "Likely incumbent is the strongest historical match, not a confirmed current contract holder." if grouped else "No matching award evidence is stored yet.",
    }
