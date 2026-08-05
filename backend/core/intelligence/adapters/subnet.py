from django.conf import settings

from .base import ConnectorHealth, IntelligenceAdapter


class SubnetAdapter(IntelligenceAdapter):
    key = "subnet"
    label = "SBA SUBNet"

    def health(self, probe: bool = False) -> ConnectorHealth:
        configured = bool(getattr(settings, "SBA_SUBNET_URL", ""))
        return ConnectorHealth(
            key=self.key,
            label=self.label,
            configured=configured,
            reachable=None,
            status="healthy" if configured else "configuration_required",
            detail="Public SBA subcontracting listing; ForgeGov normalizes HTML results.",
            official_url="https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
            authentication="No API key",
        )
