from .base import ConnectorHealth, IntelligenceAdapter
from ...live_web import status as live_web_status


class SearxngAdapter(IntelligenceAdapter):
    key = "searxng"
    label = "Live Web Search"

    def health(self, probe: bool = False) -> ConnectorHealth:
        result = live_web_status(probe=probe)
        status = str(result.get("status") or "not_configured")
        detail_map = {
            "live": "Private live-web search is reachable and returning normalized JSON results.",
            "degraded": "Live web is degraded; ForgeGov can use cached query results while the private service recovers.",
            "unavailable": "The private live-web service is configured but currently unavailable.",
            "configured": "Private live-web search is configured; run a probe to verify reachability.",
            "not_configured": "Provision the ForgeGov SearXNG private service or set SEARXNG_URL.",
        }
        if result.get("last_error_category") == "json_format_disabled":
            detail = "SearXNG is reachable but JSON output is disabled. Add json to search.formats in settings.yml."
        else:
            detail = detail_map.get(status, "Live web status could not be determined.")
        return ConnectorHealth(
            key=self.key,
            label=self.label,
            configured=bool(result.get("configured")),
            reachable=result.get("reachable"),
            status="healthy" if status == "live" else status,
            detail=detail,
            official_url="https://docs.searxng.org/dev/search_api.html",
            authentication="Private internal service",
        )
