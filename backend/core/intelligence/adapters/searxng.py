from django.conf import settings
import requests
from .base import ConnectorHealth, IntelligenceAdapter

class SearxngAdapter(IntelligenceAdapter):
    key = "searxng"
    label = "Live Web Search"

    def health(self, probe: bool = False) -> ConnectorHealth:
        url = str(getattr(settings, "SEARXNG_URL", "") or "").rstrip("/")
        configured = bool(url) and bool(getattr(settings, "AI_WEB_SEARCH_ENABLED", True))
        reachable = None
        detail = "Set SEARXNG_URL and enable JSON output in SearXNG settings."
        status = "configuration_required"
        if configured:
            status = "configured"
            detail = "SearXNG is configured; run a probe to verify JSON search access."
        if configured and probe:
            try:
                response = requests.get(f"{url}/search", params={"q":"ForgeGov connector health","format":"json"}, timeout=12)
                reachable = response.ok and response.headers.get("content-type", "").lower().startswith("application/json")
                if response.status_code == 403:
                    detail = "SearXNG is reachable but JSON output is disabled. Add json to search.formats in settings.yml."
                elif reachable:
                    detail = "Private live-web search is reachable and returning JSON."
                else:
                    detail = f"SearXNG returned HTTP {response.status_code} or a non-JSON response."
                status = "healthy" if reachable else "degraded"
            except Exception as exc:
                reachable = False
                status = "degraded"
                detail = f"SearXNG could not be reached: {exc}"
        return ConnectorHealth(key=self.key,label=self.label,configured=configured,reachable=reachable,status=status,detail=detail,official_url="https://docs.searxng.org/dev/search_api.html",authentication="Private internal service")
