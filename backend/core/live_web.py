from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import requests

from .integration_resilience import ConnectorCircuitOpen, resilient_request

_PROVIDER = "searxng"
_STATUS_KEY = "forgegov:live-web:status:v321"
_QUERY_PREFIX = "forgegov:live-web:query:v321:"
_DEFAULT_CACHE_SECONDS = 600


def configured() -> bool:
    return bool(getattr(settings, "AI_WEB_SEARCH_ENABLED", True) and str(getattr(settings, "SEARXNG_URL", "") or "").strip())


def _endpoint() -> str:
    base = str(getattr(settings, "SEARXNG_URL", "") or "").strip().rstrip("/")
    if not base:
        return ""
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return base + "/search"


def _query(value: str) -> str:
    compact = " ".join(str(value or "").split())
    return compact[:500] or "federal contracting"


def _cache_key(query: str, limit: int) -> str:
    digest = hashlib.sha256(f"{query}|{limit}".encode()).hexdigest()
    return _QUERY_PREFIX + digest


def _clean_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    # Strip fragments so the same source is not shown multiple times.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))[:2000]


def _normalize(rows: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = _clean_url(row.get("url"))
        title = " ".join(str(row.get("title") or "Live web result").split())[:500]
        snippet = " ".join(str(row.get("content") or row.get("snippet") or "").split())[:1800]
        dedupe = (url or title.lower()).strip()
        if not dedupe or dedupe in seen:
            continue
        seen.add(dedupe)
        output.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "engine": str(row.get("engine") or "")[:80],
            "category": str(row.get("category") or "")[:80],
            "publishedDate": str(row.get("publishedDate") or row.get("published_date") or "")[:80],
        })
        if len(output) >= limit:
            break
    return output


def _cached_status() -> dict[str, Any]:
    value = cache.get(_STATUS_KEY)
    return value if isinstance(value, dict) else {}


def _set_status(*, status: str, reachable: bool | None, latency_ms: int | None = None, error_category: str = "", last_success_at: str = "") -> dict[str, Any]:
    previous = _cached_status()
    payload = {
        "provider": _PROVIDER,
        "configured": configured(),
        "reachable": reachable,
        "status": status,
        "latency_ms": latency_ms,
        "last_success_at": last_success_at or previous.get("last_success_at") or "",
        "last_error_category": error_category,
        "cached_fallback_available": bool(previous.get("cached_fallback_available")),
        "checked_at": timezone.now().isoformat(),
    }
    cache.set(_STATUS_KEY, payload, 3600)
    return payload


def search(query: str, *, limit: int = 8, timeout: int = 12, allow_cached: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 8), 12))
    normalized_query = _query(query)
    key = _cache_key(normalized_query, limit)
    cached = cache.get(key)
    endpoint = _endpoint()
    if not configured() or not endpoint:
        return {
            "provider": _PROVIDER,
            "status": "not_configured",
            "reachable": False,
            "cache_used": False,
            "results": [],
            "latency_ms": None,
            "warning": "Live web search is not configured for this ForgeGov environment.",
        }

    started = time.perf_counter()
    error_category = ""
    try:
        response = resilient_request(
            _PROVIDER,
            "GET",
            endpoint,
            params={"q": normalized_query, "format": "json", "language": "en-US", "safesearch": 1},
            timeout=timeout,
            headers={"User-Agent": "ForgeGov/3.2.1"},
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.status_code == 403:
            error_category = "json_format_disabled"
            raise requests.HTTPError("SearXNG JSON output is disabled.", response=response)
        response.raise_for_status()
        payload = response.json()
        rows = _normalize(payload.get("results"), limit)
        if not isinstance(payload.get("results"), list):
            error_category = "invalid_response"
            raise ValueError("SearXNG did not return a JSON results list.")
        now = timezone.now().isoformat()
        result = {
            "provider": _PROVIDER,
            "status": "live",
            "reachable": True,
            "cache_used": False,
            "results": rows,
            "latency_ms": latency_ms,
            "warning": "",
            "retrieved_at": now,
        }
        cache.set(key, result, int(getattr(settings, "LIVE_WEB_CACHE_SECONDS", _DEFAULT_CACHE_SECONDS)))
        status_payload = _set_status(status="live", reachable=True, latency_ms=latency_ms, last_success_at=now)
        status_payload["cached_fallback_available"] = True
        cache.set(_STATUS_KEY, status_payload, 3600)
        return result
    except ConnectorCircuitOpen:
        error_category = "circuit_open"
    except requests.Timeout:
        error_category = "timeout"
    except requests.ConnectionError:
        error_category = "connection_error"
    except requests.HTTPError as exc:
        if not error_category:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            error_category = f"http_{code}" if code else "http_error"
    except (ValueError, TypeError):
        if not error_category:
            error_category = "invalid_response"
    except requests.RequestException:
        error_category = "request_error"

    latency_ms = round((time.perf_counter() - started) * 1000)
    if allow_cached and isinstance(cached, dict) and isinstance(cached.get("results"), list):
        _set_status(status="degraded", reachable=False, latency_ms=latency_ms, error_category=error_category)
        return {
            **cached,
            "status": "degraded",
            "reachable": False,
            "cache_used": True,
            "latency_ms": latency_ms,
            "warning": "Live web search is temporarily unavailable. ForgeGov is showing the latest cached web results for this query.",
        }

    _set_status(status="unavailable", reachable=False, latency_ms=latency_ms, error_category=error_category)
    return {
        "provider": _PROVIDER,
        "status": "unavailable",
        "reachable": False,
        "cache_used": False,
        "results": [],
        "latency_ms": latency_ms,
        "warning": "Live web search is temporarily unavailable. Government connectors and stored ForgeGov intelligence remain available.",
    }


def status(*, probe: bool = False) -> dict[str, Any]:
    if not configured() or not _endpoint():
        return {
            "provider": _PROVIDER,
            "configured": False,
            "reachable": False,
            "status": "not_configured",
            "latency_ms": None,
            "last_success_at": "",
            "last_error_category": "",
            "cached_fallback_available": False,
            "checked_at": timezone.now().isoformat(),
        }
    if probe:
        result = search("federal acquisition forecast", limit=1, timeout=8, allow_cached=False)
        current = _cached_status()
        return {**current, "configured": True, "reachable": result.get("reachable"), "status": result.get("status")}
    cached = _cached_status()
    if cached:
        return {**cached, "configured": True}
    return {
        "provider": _PROVIDER,
        "configured": True,
        "reachable": None,
        "status": "configured",
        "latency_ms": None,
        "last_success_at": "",
        "last_error_category": "",
        "cached_fallback_available": False,
        "checked_at": "",
    }


def grounding(query: str, *, limit: int = 8) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    result = search(query, limit=limit)
    lines: list[str] = []
    sources: list[dict[str, str]] = []
    for index, row in enumerate(result.get("results") or [], 1):
        label = f"WEB-{index}"
        lines.append(f"[{label}] title={row.get('title','')} | url={row.get('url','')} | snippet={row.get('snippet','')}")
        sources.append({"label": label, "type": "web", "title": str(row.get("title") or "Live web result"), "url": str(row.get("url") or "")})
    return "\n".join(lines), sources, result
