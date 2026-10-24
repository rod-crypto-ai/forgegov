"""Read-only reports from stored public awards, separate from private capture forecasts."""
from datetime import timedelta

from django.db.models import Count, Max, Min, Sum
from django.utils import timezone

from .models import Award, AwardSyncRun


def market_report(*, kind, agency="", naics="", days=90, page=1, page_size=25):
    today = timezone.localdate()
    cutoff = today - timedelta(days=days)
    awards = Award.objects.filter(source="usaspending.gov", jurisdiction_level="federal")
    if agency:
        awards = awards.filter(awarding_agency__icontains=agency)
    if naics:
        awards = awards.filter(naics_code=naics)
    totals = awards.aggregate(records=Count("id"), obligated=Sum("obligated_amount"), latest_source_update=Max("source_updated_at"))
    if kind == "new-entrants":
        # Group the entire stored history BEFORE applying the recent-window condition.
        # Otherwise a repeat recipient's recent award would look like its first award.
        groups = awards.exclude(recipient_name="").filter(start_date__lte=today).values(
            "recipient_name", "recipient_uei", "awarding_agency",
        ).annotate(first_award=Min("start_date"), latest_award=Max("start_date"), award_count=Count("id"), obligated=Sum("obligated_amount"))
        groups = groups.filter(first_award__gte=cutoff).order_by("-first_award", "recipient_name", "recipient_uei", "awarding_agency")
    else:
        groups = awards.values("awarding_agency").annotate(award_count=Count("id"), obligated=Sum("obligated_amount"), recipients=Count("recipient_name", distinct=True)).order_by("-obligated", "awarding_agency")
    count = groups.count()
    total_pages = max(1, (count + page_size - 1) // page_size)
    page = min(page, total_pages)
    rows = list(groups[(page - 1) * page_size:page * page_size])
    total_obligated = float(totals["obligated"] or 0)
    for row in rows:
        row["obligated"] = float(row["obligated"] or 0)
        if kind == "funding":
            row["share_percent"] = round(row["obligated"] / total_obligated * 100, 2) if total_obligated else None
    sync = AwardSyncRun.objects.filter(connector_key="usaspending-awards").order_by("-started_at", "-id").first()
    return {
        "kind": kind, "classification": "stored_official_award_history", "source": "USAspending.gov",
        "generated_at": timezone.now(), "window_start": cutoff, "window_end": today,
        "filters": {"agency": agency, "naics": naics, "days": days},
        "totals": {**totals, "obligated": total_obligated},
        "sync": {"status": sync.status if sync else "not_run", "last_completed_at": sync.completed_at if sync else None},
        "count": count, "page": page, "page_size": page_size, "total_pages": total_pages,
        "results": rows,
        "coverage_note": "Stored federal award history only, not a live market total. First observed means the earliest dated award for a recipient/agency pair within the selected stored market; incomplete history, missing UEIs, and recipient name changes can affect this signal. It does not establish that a company is new to government contracting.",
    }
