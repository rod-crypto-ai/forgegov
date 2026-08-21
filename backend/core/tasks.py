from datetime import date, timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .integrations import IntegrationError, search_grants_opportunities, search_sam_opportunities, usaspending_status
from .models import (
    CollaborationNotification,
    DataSyncRun,
    IntelligenceAlert,
    Membership,
    NotificationDelivery,
    NotificationPreference,
    Opportunity,
    Organization,
    PipelineItem,
    SavedSearch,
    SourceRecordVersion,
    Task,
)
from .notifications import create_notification, notification_preference, category_enabled, platform_notifications_enabled, send_tracked_email


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
            sync_run=run,
        )
        persisted = result["persisted"]
        run.request_metadata = {**(run.request_metadata or {}), "integrity": {
            "unchanged": persisted.get("unchanged", 0),
            "quarantined": persisted.get("quarantined", 0),
        }}
        run.status = DataSyncRun.Status.PARTIAL if persisted.get("quarantined") else DataSyncRun.Status.SUCCESS
        run.records_received = len(result["opportunities"])
        run.records_created = persisted["created"]
        run.records_updated = persisted["updated"]
        run.error_message = " | ".join(persisted.get("errors") or [])[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=[
            "status",
            "records_received",
            "records_created",
            "records_updated",
            "error_message",
            "finished_at",
            "request_metadata",
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
            sync_run=run,
        )
        persisted = result["persisted"]
        run.request_metadata = {**(run.request_metadata or {}), "integrity": {
            "unchanged": persisted.get("unchanged", 0),
            "quarantined": persisted.get("quarantined", 0),
        }}
        run.status = DataSyncRun.Status.PARTIAL if persisted.get("quarantined") else DataSyncRun.Status.SUCCESS
        run.records_received = len(result["results"])
        run.records_created = persisted["created"]
        run.records_updated = persisted["updated"]
        run.error_message = " | ".join(persisted.get("errors") or [])[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "records_received", "records_created", "records_updated", "error_message", "finished_at", "request_metadata", "updated_at"])
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
            alert, was_created = IntelligenceAlert.objects.get_or_create(
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
                    "event_key": f"saved:{saved.id}:new:{source_id}"[:255],
                },
            )
            if was_created:
                _fanout_intelligence_alert(alert, category="opportunity", critical=False)
            created += int(was_created)
    return {"saved_searches_evaluated": evaluated, "alerts_created": created}


def _alert_link(alert: IntelligenceAlert) -> str:
    if alert.opportunity_id and alert.opportunity and alert.opportunity.source == "sam.gov":
        return f"/opportunities/federal-contracts/{alert.opportunity.source_id}"
    if alert.opportunity_id and alert.opportunity and alert.opportunity.source == "grants.gov":
        return f"/opportunities/federal-grants/{alert.opportunity.source_id}"
    return "/capture/alerts"


def _fanout_intelligence_alert(alert: IntelligenceAlert, *, category: str, critical: bool) -> int:
    sent = 0
    memberships = Membership.objects.filter(organization=alert.organization, active=True).select_related("user")
    for membership in memberships:
        pref = notification_preference(organization=alert.organization, user=membership.user)
        if not category_enabled(pref, category):
            continue
        if pref.in_app_enabled:
            create_notification(
                organization=alert.organization,
                user=membership.user,
                title=alert.title,
                message=alert.summary,
                kind=f"intelligence_{alert.alert_type}",
                link=_alert_link(alert),
                category=category,
            )
        if critical and pref.email_enabled and pref.immediate_critical:
            sent += int(send_tracked_email(
                subject=f"ForgeGov alert: {alert.title}",
                message=f"{alert.summary}\n\nOpen ForgeGov: {_alert_link(alert)}",
                recipient=getattr(membership.user, "email", ""),
                organization=alert.organization,
                user=membership.user,
                category=category,
                related_object_type="intelligence_alert",
                related_object_id=alert.id,
            ))
    return sent


def _create_event_alert(*, organization, opportunity=None, alert_type, title, summary, event_key, category, critical=False, matched_filters=None):
    alert = IntelligenceAlert.objects.filter(organization=organization, event_key=event_key).first()
    if alert:
        return alert, False
    alert = IntelligenceAlert.objects.create(
        organization=organization,
        opportunity=opportunity,
        alert_type=alert_type,
        title=title[:500],
        summary=summary,
        source_id=(opportunity.source_id if opportunity else "")[:255],
        source_url=(opportunity.source_url if opportunity else ""),
        matched_filters=matched_filters or {},
        event_key=event_key[:255],
    )
    _fanout_intelligence_alert(alert, category=category, critical=critical)
    return alert, True


@shared_task
def evaluate_deadline_alerts(organization_id: int | None = None):
    now = timezone.now()
    horizon = now + timedelta(days=7)
    memberships = Membership.objects.filter(active=True)
    org_ids = memberships.values_list("organization_id", flat=True).distinct()
    if organization_id is not None:
        org_ids = org_ids.filter(organization_id=organization_id)
    created = 0
    for org_id in org_ids:
        pipeline = PipelineItem.objects.filter(organization_id=org_id).select_related("opportunity")
        for item in pipeline:
            deadline = item.opportunity.response_deadline
            if deadline and now <= deadline <= horizon:
                key = f"opp-deadline:{item.opportunity_id}:{deadline.isoformat()}"
                days = max(0, (deadline.date() - now.date()).days)
                _, was_created = _create_event_alert(
                    organization=item.organization,
                    opportunity=item.opportunity,
                    alert_type=IntelligenceAlert.AlertType.DEADLINE,
                    title=f"Response deadline approaching: {item.opportunity.title}",
                    summary=f"Response deadline is {deadline.isoformat()} ({days} day{'s' if days != 1 else ''} remaining).",
                    event_key=key,
                    category="deadline",
                    critical=days <= 1,
                )
                created += int(was_created)
            if item.follow_up_date and now.date() <= item.follow_up_date <= horizon.date():
                key = f"pipeline-followup:{item.id}:{item.follow_up_date.isoformat()}"
                _, was_created = _create_event_alert(
                    organization=item.organization,
                    opportunity=item.opportunity,
                    alert_type=IntelligenceAlert.AlertType.PIPELINE,
                    title=f"Pipeline follow-up due: {item.opportunity.title}",
                    summary=f"Follow-up is scheduled for {item.follow_up_date.isoformat()}. {item.next_action or ''}".strip(),
                    event_key=key,
                    category="pipeline",
                    critical=item.follow_up_date <= now.date(),
                )
                created += int(was_created)
        tasks = Task.objects.filter(organization_id=org_id, completed=False, due_at__isnull=False, due_at__lte=horizon).select_related("pipeline_item__opportunity", "assigned_to")
        for task in tasks:
            key = f"task-deadline:{task.id}:{task.due_at.isoformat()}"
            opportunity = task.pipeline_item.opportunity if task.pipeline_item_id else None
            alert, was_created = _create_event_alert(
                organization=task.organization,
                opportunity=opportunity,
                alert_type=IntelligenceAlert.AlertType.DEADLINE,
                title=f"Task due: {task.title}",
                summary=f"Task deadline is {task.due_at.isoformat()}.",
                event_key=key,
                category="deadline",
                critical=task.due_at <= now + timedelta(days=1),
            )
            if was_created and task.assigned_to_id:
                # The organization-wide alert remains visible, while assignment is explicit in the collaboration inbox.
                create_notification(
                    organization=task.organization,
                    user=task.assigned_to,
                    title=alert.title,
                    message=alert.summary,
                    kind="task_deadline",
                    link=f"/capture/tasks",
                    category="deadline",
                )
            created += int(was_created)
    return {"alerts_created": created}


def _value(payload, *keys):
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return None


def _resource_ids(payload):
    links = _value(payload, "resourceLinks", "resource_links", "attachments") or []
    if not isinstance(links, list):
        return set()
    values = set()
    for row in links:
        if isinstance(row, dict):
            values.add(str(row.get("url") or row.get("resourceURL") or row.get("name") or row))
        else:
            values.add(str(row))
    return values


@shared_task
def evaluate_opportunity_change_alerts(organization_id: int | None = None):
    org_ids = Membership.objects.filter(active=True).values_list("organization_id", flat=True).distinct()
    if organization_id is not None:
        org_ids = org_ids.filter(organization_id=organization_id)
    created = 0
    for org_id in org_ids:
        opportunity_ids = set(PipelineItem.objects.filter(organization_id=org_id).values_list("opportunity_id", flat=True))
        opportunity_ids.update(IntelligenceAlert.objects.filter(organization_id=org_id, opportunity__isnull=False).values_list("opportunity_id", flat=True))
        for opportunity in Opportunity.objects.filter(id__in=opportunity_ids):
            versions = list(SourceRecordVersion.objects.filter(source_id=opportunity.source_id, record_type__startswith="opportunity.").order_by("-observed_at", "-id")[:2])
            if len(versions) < 2:
                continue
            latest, previous = versions[0], versions[1]
            if latest.fingerprint == previous.fingerprint:
                continue
            old = previous.raw_data or {}
            new = latest.raw_data or {}
            changes = []
            old_deadline = _value(old, "responseDeadLine", "responseDeadline", "closeDate")
            new_deadline = _value(new, "responseDeadLine", "responseDeadline", "closeDate")
            if old_deadline != new_deadline and new_deadline:
                changes.append((IntelligenceAlert.AlertType.DEADLINE_CHANGED, "Response deadline changed", f"Response deadline changed from {old_deadline or 'not set'} to {new_deadline}.", "deadline", True))
            old_set_aside = _value(old, "typeOfSetAsideDescription", "setAside", "set_aside")
            new_set_aside = _value(new, "typeOfSetAsideDescription", "setAside", "set_aside")
            if old_set_aside != new_set_aside and new_set_aside:
                changes.append((IntelligenceAlert.AlertType.SET_ASIDE_CHANGED, "Set-aside changed", f"Set-aside changed from {old_set_aside or 'not set'} to {new_set_aside}.", "opportunity_change", True))
            old_active = str(_value(old, "active", "status") or "").lower()
            new_active = str(_value(new, "active", "status") or "").lower()
            if old_active != new_active and new_active in {"false", "no", "0", "cancelled", "canceled", "inactive"}:
                changes.append((IntelligenceAlert.AlertType.CANCELLED, "Opportunity cancelled or inactive", "The source now reports this opportunity as cancelled or inactive.", "opportunity_change", True))
            added_resources = _resource_ids(new) - _resource_ids(old)
            if added_resources:
                changes.append((IntelligenceAlert.AlertType.DOCUMENT, "New opportunity attachment", f"{len(added_resources)} new attachment{'s' if len(added_resources) != 1 else ''} detected.", "opportunity_change", False))
            if not changes:
                changes.append((IntelligenceAlert.AlertType.AMENDMENT, "Opportunity updated", "ForgeGov detected a new source version for this opportunity.", "opportunity_change", False))
            for alert_type, label, detail, category, critical in changes:
                key = f"source-change:{opportunity.source_id}:{latest.fingerprint}:{alert_type}"
                organization = Organization.objects.filter(pk=org_id).first()
                if not organization:
                    continue
                _, was_created = _create_event_alert(
                    organization=organization,
                    opportunity=opportunity,
                    alert_type=alert_type,
                    title=f"{label}: {opportunity.title}",
                    summary=detail,
                    event_key=key,
                    category=category,
                    critical=critical,
                    matched_filters={"source_version": latest.fingerprint},
                )
                created += int(was_created)
    return {"alerts_created": created}


def _digest_message(*, membership, since):
    org = membership.organization
    alerts = IntelligenceAlert.objects.filter(organization=org, created_at__gte=since, dismissed=False).order_by("-created_at")[:25]
    notifications = CollaborationNotification.objects.filter(
        organization=org,
        created_at__gte=since,
    ).filter(Q(user=membership.user) | Q(user__isnull=True)).order_by("-created_at")[:25]
    open_tasks = Task.objects.filter(organization=org, completed=False, due_at__isnull=False, due_at__lte=timezone.now() + timedelta(days=7)).order_by("due_at")[:10]
    if not alerts and not notifications and not open_tasks:
        return ""
    lines = [f"ForgeGov intelligence brief for {org.name}", ""]
    if alerts:
        lines.append("INTELLIGENCE")
        lines.extend(f"- {row.title}: {row.summary}" for row in alerts)
        lines.append("")
    if open_tasks:
        lines.append("DEADLINES")
        lines.extend(f"- {row.title} — due {row.due_at.isoformat()}" for row in open_tasks)
        lines.append("")
    if notifications:
        lines.append("WORKSPACE ACTIVITY")
        lines.extend(f"- {row.title}: {row.message}" for row in notifications)
        lines.append("")
    lines.append("Open ForgeGov to review and act on these items.")
    return "\n".join(lines)


def _send_digest(*, period: str):
    now = timezone.now()
    since = now - timedelta(days=1 if period == "daily" else 7)
    sent = skipped = failed = 0
    memberships = Membership.objects.filter(active=True).select_related("user", "organization")
    for membership in memberships:
        pref = notification_preference(organization=membership.organization, user=membership.user)
        enabled = pref.daily_digest if period == "daily" else pref.weekly_digest
        if not (pref.email_enabled and enabled):
            skipped += 1
            continue
        already = NotificationDelivery.objects.filter(
            organization=membership.organization,
            user=membership.user,
            category=f"{period}_digest",
            status=NotificationDelivery.Status.SENT,
            created_at__gte=since,
        ).exists()
        if already:
            skipped += 1
            continue
        message = _digest_message(membership=membership, since=since)
        if not message:
            skipped += 1
            continue
        recipient = getattr(membership.user, "email", "")
        delivery_enabled = platform_notifications_enabled() and bool(recipient)
        ok = send_tracked_email(
            subject=f"ForgeGov {period.title()} Intelligence Brief",
            message=message,
            recipient=recipient,
            organization=membership.organization,
            user=membership.user,
            category=f"{period}_digest",
            related_object_type="digest",
            related_object_id=now.date().isoformat(),
        )
        if ok:
            sent += 1
        elif delivery_enabled:
            failed += 1
        else:
            skipped += 1
    return {"sent": sent, "skipped": skipped, "failed": failed}


@shared_task
def send_daily_intelligence_digests():
    return _send_digest(period="daily")


@shared_task
def send_weekly_intelligence_digests():
    return _send_digest(period="weekly")

