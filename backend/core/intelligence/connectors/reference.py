from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from .base import ConnectorDescriptor, ProcurementConnector


class RegisteredSourceConnector(ProcurementConnector):
    """Health metadata for official sources served by existing live adapters."""

    def __init__(self, descriptor: ConnectorDescriptor, *, setting: str = ""):
        self.descriptor = descriptor
        self.setting = setting

    def health(self):
        configured = bool(getattr(settings, self.setting, "")) if self.setting else True
        return {
            **self.descriptor.to_dict(),
            "configured": configured,
            "reachable": None,
            "status": "configured_not_verified" if configured else "configuration_required",
            "detail": "Configured, but this registry check does not claim live-source reachability." if configured else "Required connector configuration is missing.",
            "checked_at": timezone.now().isoformat(),
        }


def source(key, name, scope, url, capabilities, *, authentication="Public source", setting=""):
    return RegisteredSourceConnector(ConnectorDescriptor(
        key=key, name=name, scope=scope, jurisdiction_code="US", jurisdiction_name="United States",
        official_url=url, authentication=authentication, capabilities=capabilities,
        license_name="U.S. Government public data",
    ), setting=setting)


registered_sources = (
    source("sam-opportunities", "SAM.gov Opportunities", "federal", "https://sam.gov/content/opportunities", ["opportunities", "documents"], authentication="SAM.gov API key", setting="SAM_GOV_API_KEY"),
    source("grants-opportunities", "Grants.gov Opportunities", "federal", "https://www.grants.gov/search-grants", ["grants", "opportunities", "documents"]),
    source("sba-subnet", "SBA SUBNet", "federal", "https://subnet.sba.gov/", ["subcontracting_opportunities"]),
    source("federal-forecasts", "Federal Procurement Forecasts", "federal", "https://www.acquisition.gov/procurement-forecasts", ["procurement_forecasts"]),
    source("usaspending-vehicles", "USAspending Contract Vehicles", "federal", "https://www.usaspending.gov/", ["idv", "contract_vehicles"]),
    source("state-local-directory", "State & Local Source Directory", "state_local", "https://www.naspo.org/", ["source_directory", "state_local_status"]),
)
