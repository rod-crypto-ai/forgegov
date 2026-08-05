from django.conf import settings

from .base import ConnectorHealth, IntelligenceAdapter


class SamAdapter(IntelligenceAdapter):
    key = "sam"
    label = "SAM.gov"

    def health(self, probe: bool = False) -> ConnectorHealth:
        configured = bool(settings.SAM_GOV_API_KEY)
        return ConnectorHealth(
            key=self.key,
            label=self.label,
            configured=configured,
            reachable=None if not probe else configured,
            status="healthy" if configured else "configuration_required",
            detail="Contract opportunity and entity APIs are available." if configured else "Add a SAM.gov public API key.",
            official_url="https://sam.gov/content/entity-information",
            authentication="API key",
        )
