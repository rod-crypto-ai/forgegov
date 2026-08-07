from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from django.utils import timezone

from ...integrations import search_usaspending_awards, usaspending_status
from .base import ConnectorDescriptor, ProcurementConnector


class UsaSpendingAwardConnector(ProcurementConnector):
    descriptor = ConnectorDescriptor(
        key="usaspending-awards",
        name="USAspending Federal Awards",
        scope="federal",
        jurisdiction_code="US",
        jurisdiction_name="United States",
        official_url="https://www.usaspending.gov/",
        documentation_url="https://api.usaspending.gov/docs/endpoints",
        license_name="U.S. Government public data",
        license_url="https://www.usa.gov/government-copyright",
        authentication="No API key",
        capabilities=["awards", "incumbents", "past_winners", "agency_spending", "contractor_history"],
        rate_limit="Public API; ForgeGov uses bounded pages and incremental windows",
    )

    def health(self) -> dict[str, Any]:
        result = usaspending_status(probe=True)
        return {
            **self.descriptor.to_dict(),
            "configured": True,
            "reachable": result.get("reachable"),
            "status": "healthy" if result.get("reachable") else "degraded",
            "detail": result.get("detail") or "Official federal award and spending API.",
            "checked_at": timezone.now().isoformat(),
        }

    def iter_awards(self, **filters: Any) -> Iterable[dict[str, Any]]:
        start_date = filters.get("start_date") or f"{date.today().year - 1}-01-01"
        end_date = filters.get("end_date") or date.today().isoformat()
        pages = max(1, min(int(filters.get("pages") or 1), 50))
        limit = max(1, min(int(filters.get("limit") or 100), 100))
        for page in range(1, pages + 1):
            payload = search_usaspending_awards(
                keyword=filters.get("keyword", ""),
                recipient=filters.get("recipient", ""),
                agency=filters.get("agency", ""),
                naics=filters.get("naics", ""),
                start_date=start_date,
                end_date=end_date,
                page=page,
                limit=limit,
                persist=False,
            )
            rows = payload.get("results") or []
            for row in rows:
                if isinstance(row, dict):
                    yield row
            metadata = payload.get("page_metadata") or {}
            if metadata and not metadata.get("hasNext", metadata.get("has_next", False)):
                break
            if len(rows) < limit:
                break
