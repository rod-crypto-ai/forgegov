from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from .base import ConnectorDescriptor, ProcurementConnector


class RegisteredSourceConnector(ProcurementConnector):
    """Health metadata for official sources served by existing live adapters."""

    def __init__(self, descriptor: ConnectorDescriptor, *, setting: str = "", reference_only: bool = False):
        self.descriptor = descriptor
        self.setting = setting
        self.reference_only = reference_only

    def health(self, probe: bool = False):
        configured = bool(getattr(settings, self.setting, "")) if self.setting else True
        if self.reference_only:
            return {
                **self.descriptor.to_dict(),
                "configured": True,
                "reachable": None,
                "status": "reference_only",
                "detail": "Official-source directory only; no machine-readable opportunity feed is claimed.",
                "checked_at": timezone.now().isoformat() if probe else None,
            }
        if not configured:
            return {
                **self.descriptor.to_dict(),
                "configured": False,
                "reachable": None,
                "status": "configuration_required",
                "detail": "Required connector configuration is missing.",
                "checked_at": timezone.now().isoformat() if probe else None,
            }
        if not probe:
            return {
                **self.descriptor.to_dict(),
                "configured": True,
                "reachable": None,
                "status": "not_verified",
                "detail": "Configured; run a probe to verify current source reachability.",
                "checked_at": None,
            }
        status, reachable, detail = self._probe()
        return {
            **self.descriptor.to_dict(),
            "configured": True,
            "reachable": reachable,
            "status": status,
            "detail": detail,
            "checked_at": timezone.now().isoformat(),
        }

    def _probe(self) -> tuple[str, bool | None, str]:
        try:
            if self.descriptor.key == "sam-opportunities":
                from ...integrations import search_sam_opportunities
                search_sam_opportunities(limit=1, persist=False)
                return "healthy", True, "SAM.gov opportunity search responded successfully."
            if self.descriptor.key == "grants-opportunities":
                from ...integrations import search_grants_opportunities
                search_grants_opportunities(limit=1, persist=False)
                return "healthy", True, "Grants.gov opportunity search responded successfully."
            if self.descriptor.key == "sba-subnet":
                from ...integrations import search_sba_subnet_opportunities
                result = search_sba_subnet_opportunities(page=0, page_size=1)
                source_status = str(result.get("status") or "unavailable")
                if source_status == "live":
                    return "healthy", True, "The official SBA opportunity directory responded successfully."
                if source_status in {"indexed", "cached"}:
                    return "degraded", False, str(result.get("warning") or "Verified fallback data is available while direct SBA access recovers.")
                return "unavailable", False, str(result.get("warning") or "The SBA opportunity source is unavailable.")
            if self.descriptor.key == "federal-forecasts":
                from ...integrations import search_federal_forecast_sources
                result = search_federal_forecast_sources()
                if result.get("reachable"):
                    return "healthy", True, "The Acquisition.gov forecast directory responded successfully."
                return "degraded", False, "The live directory is unavailable; the official fallback link remains available."
            if self.descriptor.key == "usaspending-vehicles":
                from ...integrations import search_usaspending_contract_vehicles
                search_usaspending_contract_vehicles(page=1, limit=1, persist=False)
                return "healthy", True, "USAspending contract-vehicle search responded successfully."
            if self.descriptor.key == "live-web-search":
                from ...live_web import status as live_web_status
                result = live_web_status(probe=True)
                live = result.get("status") == "live" and result.get("reachable") is True
                return ("healthy" if live else str(result.get("status") or "unavailable"), result.get("reachable"), "Private live-web search responded successfully." if live else "Private live-web search is not currently available.")
        except Exception:
            return "unavailable", False, "The configured source did not complete its health probe."
        return "not_verified", None, "No live probe is implemented for this source."


def source(key, name, scope, url, capabilities, *, authentication="Public source", setting="", reference_only=False):
    return RegisteredSourceConnector(ConnectorDescriptor(
        key=key, name=name, scope=scope, jurisdiction_code="US", jurisdiction_name="United States",
        official_url=url, authentication=authentication, capabilities=capabilities,
        license_name="U.S. Government public data",
    ), setting=setting, reference_only=reference_only)


registered_sources = (
    source("sam-opportunities", "SAM.gov Opportunities", "federal", "https://sam.gov/content/opportunities", ["opportunities", "documents"], authentication="SAM.gov API key", setting="SAM_GOV_API_KEY"),
    source("grants-opportunities", "Grants.gov Opportunities", "federal", "https://www.grants.gov/search-grants", ["grants", "opportunities", "documents"]),
    source("sba-subnet", "SBA SUBNet", "federal", "https://subnet.sba.gov/", ["subcontracting_opportunities"]),
    source("federal-forecasts", "Federal Procurement Forecasts", "federal", "https://www.acquisition.gov/procurement-forecasts", ["procurement_forecasts"]),
    source("usaspending-vehicles", "USAspending Contract Vehicles", "federal", "https://www.usaspending.gov/", ["idv", "contract_vehicles"]),
    source("state-local-directory", "State & Local Source Directory", "state", "https://www.naspo.org/", ["source_directory", "state_local_status"], reference_only=True),
    source("live-web-search", "ForgeGov Live Web Search", "commercial", "https://docs.searxng.org/dev/search_api.html", ["official_source_discovery", "fallback_search"], authentication="Private internal service", setting="SEARXNG_URL"),
)
