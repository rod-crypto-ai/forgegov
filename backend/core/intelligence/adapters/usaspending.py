from .base import ConnectorHealth, IntelligenceAdapter
from ...integrations import usaspending_status


class UsaSpendingAdapter(IntelligenceAdapter):
    key = "usaspending"
    label = "USAspending"

    def health(self, probe: bool = False) -> ConnectorHealth:
        result = usaspending_status(probe=probe)
        reachable = result.get("reachable")
        return ConnectorHealth(
            key=self.key,
            label=self.label,
            configured=True,
            reachable=reachable,
            status="healthy" if reachable is not False else "degraded",
            detail="Public award and spending API.",
            official_url="https://api.usaspending.gov/",
            authentication="No API key",
        )
