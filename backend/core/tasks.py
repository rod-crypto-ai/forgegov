from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from .integrations import IntegrationError, search_grants_opportunities, search_sam_opportunities, usaspending_status
from .models import DataSyncRun


@shared_task
def check_external_integrations():
    return {"usaspending": usaspending_status(probe=True)}


@shared_task(bind=True, autoretry_for=(IntegrationError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_recent_sam_opportunities(self, days: int = 1, limit: int = 1000):
    today = date.today()
    run = DataSyncRun.objects.create(
        source="sam.gov",
        request_metadata={"days": days, "limit": limit},
    )
    try:
        result = search_sam_opportunities(
            posted_from=(today - timedelta(days=max(1, days))).strftime("%m/%d/%Y"),
            posted_to=today.strftime("%m/%d/%Y"),
            limit=limit,
            persist=True,
        )
        persisted = result["persisted"]
        run.status = DataSyncRun.Status.SUCCESS
        run.records_received = len(result["opportunities"])
        run.records_created = persisted["created"]
        run.records_updated = persisted["updated"]
        run.finished_at = timezone.now()
        run.save(update_fields=[
            "status",
            "records_received",
            "records_created",
            "records_updated",
            "finished_at",
            "updated_at",
        ])
        return {
            "run_id": run.pk,
            "records_received": run.records_received,
            "records_created": run.records_created,
            "records_updated": run.records_updated,
        }
    except Exception as exc:
        run.status = DataSyncRun.Status.FAILED
        run.error_message = str(exc)[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        raise


@shared_task(bind=True, autoretry_for=(IntegrationError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_usaspending_awards(self, days: int = 365, limit: int = 100):
    from .integrations import search_usaspending_awards
    today = date.today()
    run = DataSyncRun.objects.create(
        source="usaspending.gov",
        request_metadata={"days": days, "limit": limit},
    )
    try:
        result = search_usaspending_awards(
            start_date=(today - timedelta(days=max(1, days))).isoformat(),
            end_date=today.isoformat(),
            limit=limit,
            persist=True,
        )
        persisted = result["persisted"]
        run.status = DataSyncRun.Status.SUCCESS
        run.records_received = len(result["results"])
        run.records_created = persisted["created"]
        run.records_updated = persisted["updated"]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "records_received", "records_created", "records_updated", "finished_at", "updated_at"])
        return {"run_id": run.pk, "records_received": run.records_received, "records_created": run.records_created, "records_updated": run.records_updated}
    except Exception as exc:
        run.status = DataSyncRun.Status.FAILED
        run.error_message = str(exc)[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        raise


@shared_task(bind=True, autoretry_for=(IntegrationError,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def evaluate_saved_search_alerts(self, organization_id: int | None = None):
    """Evaluate enabled SAM.gov and Grants.gov saved searches and create deduplicated alerts."""
    from .models import IntelligenceAlert, Opportunity, SavedSearch

    created = 0
    evaluated = 0
    searches = SavedSearch.objects.filter(enabled=True).select_related("organization")
    if organization_id is not None:
        searches = searches.filter(organization_id=organization_id)
    for saved in searches:
        filters = dict(saved.filters or {})
        source = str(filters.pop("source", "sam.gov")).lower()
        try:
            requested_limit = int(filters.get("limit") or 50)
        except (TypeError, ValueError):
            requested_limit = 50
        limit = max(1, min(requested_limit, 100))

        if source in {"grants.gov", "grants"}:
            result = search_grants_opportunities(
                keyword=filters.get("q") or filters.get("keyword") or "",
                opportunity_number=filters.get("opportunity_number") or "",
                agencies=filters.get("agency") or "",
                statuses=filters.get("statuses") or "forecasted|posted",
                aln=filters.get("aln") or "",
                funding_categories=filters.get("funding_categories") or "",
                eligibilities=filters.get("eligibilities") or "",
                funding_instruments=filters.get("funding_instruments") or "",
                limit=limit,
                persist=True,
            )
            records = result.get("opportunities", [])
        elif source in {"sam.gov", "sam"}:
            result = search_sam_opportunities(
                keyword=filters.get("q") or filters.get("keyword") or "",
                agency=filters.get("agency") or "",
                naics=filters.get("naics") or "",
                psc=filters.get("psc") or "",
                state=filters.get("state") or "",
                set_aside=filters.get("set_aside") or "",
                procurement_type=filters.get("ptype") or "",
                posted_from=filters.get("posted_from"),
                posted_to=filters.get("posted_to"),
                limit=limit,
                persist=True,
            )
            records = result.get("opportunities", [])
        else:
            continue

        evaluated += 1
        for record in records:
            source_id = str(record.get("source_id") or record.get("noticeId") or "")
            if not source_id:
                continue
            opportunity = Opportunity.objects.filter(source_id=source_id).first()
            _, was_created = IntelligenceAlert.objects.get_or_create(
                organization=saved.organization,
                saved_search=saved,
                source_id=source_id,
                alert_type=IntelligenceAlert.AlertType.NEW_OPPORTUNITY,
                defaults={
                    "opportunity": opportunity,
                    "title": str(record.get("title") or "New matching opportunity")[:500],
                    "summary": str(record.get("fullParentPathName") or record.get("agencyName") or record.get("solicitationNumber") or record.get("number") or ""),
                    "source_url": str(record.get("source_url") or ""),
                    "matched_filters": saved.filters,
                },
            )
            created += int(was_created)
    return {"saved_searches_evaluated": evaluated, "alerts_created": created}

