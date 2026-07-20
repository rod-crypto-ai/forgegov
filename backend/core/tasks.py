from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from .integrations import IntegrationError, search_sam_opportunities, usaspending_status
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
