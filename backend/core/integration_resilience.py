from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Sum
from django.utils import timezone

from .models import SourceRecordVersion, SyncQuarantine


class ConnectorCircuitOpen(requests.RequestException):
    pass


def _safe_cache_get(key: str, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        return default


def _safe_cache_set(key: str, value, timeout: int) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        pass


def _safe_cache_delete(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        pass


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def fingerprint_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _json_safe(payload: Any):
    return json.loads(_canonical_json(payload))


def _public_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return ""


def record_source_version(
    *,
    source: str,
    record_type: str,
    source_id: str,
    payload: dict[str, Any],
    source_url: str = "",
    source_modified_at=None,
    provenance: dict[str, Any] | None = None,
) -> tuple[SourceRecordVersion, bool]:
    digest = fingerprint_payload(payload)
    observed_at = timezone.now()
    metadata = {
        "source": source,
        "source_id": source_id,
        "source_url": _public_url(source_url),
        "observed_at": observed_at.isoformat(),
        "source_modified_at": source_modified_at.isoformat() if source_modified_at else None,
        "fingerprint": digest,
        **(provenance or {}),
    }
    row, created = SourceRecordVersion.objects.get_or_create(
        source=source,
        record_type=record_type,
        source_id=str(source_id)[:255],
        fingerprint=digest,
        defaults={
            "source_modified_at": source_modified_at,
            "observed_at": observed_at,
            "last_seen_at": observed_at,
            "provenance": metadata,
            "raw_data": _json_safe(payload),
        },
    )
    if not created:
        row.last_seen_at = observed_at
        row.provenance = {**(row.provenance or {}), "last_seen_at": observed_at.isoformat()}
        row.save(update_fields=["last_seen_at", "provenance", "updated_at"])
    return row, created


def quarantine_record(
    *,
    source: str,
    record_type: str,
    payload: Any,
    reason: str,
    error: Exception | str | None = None,
    source_id: str = "",
    data_sync_run=None,
    award_sync_run=None,
) -> SyncQuarantine | None:
    try:
        normalized = _json_safe(payload if isinstance(payload, dict) else {"value": payload})
        digest = fingerprint_payload(normalized)
        row, created = SyncQuarantine.objects.get_or_create(
            source=source,
            record_type=record_type,
            payload_hash=digest,
            defaults={
                "source_id": str(source_id or "")[:255],
                "reason": str(reason or "persistence_error")[:120],
                "error_message": str(error or "")[:1000],
                "raw_data": normalized,
                "data_sync_run": data_sync_run,
                "award_sync_run": award_sync_run,
            },
        )
        if not created:
            row.occurrences += 1
            row.source_id = str(source_id or row.source_id or "")[:255]
            row.reason = str(reason or row.reason)[:120]
            row.error_message = str(error or row.error_message or "")[:1000]
            row.raw_data = normalized
            row.data_sync_run = data_sync_run or row.data_sync_run
            row.award_sync_run = award_sync_run or row.award_sync_run
            row.resolved_at = None
            row.resolution_note = ""
            row.save()
        return row
    except Exception:
        return None


def resilient_request(source: str, method: str, url: str, **kwargs):
    attempts = max(1, int(getattr(settings, "CONNECTOR_RETRY_ATTEMPTS", 3)))
    base_backoff = max(0.0, float(getattr(settings, "CONNECTOR_RETRY_BACKOFF_SECONDS", 0.25)))
    threshold = max(1, int(getattr(settings, "CONNECTOR_CIRCUIT_FAILURE_THRESHOLD", 3)))
    open_seconds = max(1, int(getattr(settings, "CONNECTOR_CIRCUIT_OPEN_SECONDS", 60)))
    retry_statuses = set(getattr(settings, "CONNECTOR_RETRY_STATUS_CODES", (429, 500, 502, 503, 504)))
    circuit_key = f"forgegov:connector-circuit:{source}"
    state = _safe_cache_get(circuit_key, {}) or {}
    now = time.time()
    if float(state.get("open_until") or 0) > now:
        raise ConnectorCircuitOpen(f"{source} connector circuit is temporarily open.")

    last_exc = None
    for attempt in range(attempts):
        try:
            method_name = str(method).strip().upper()
            request_fn = requests.get if method_name == "GET" else requests.post if method_name == "POST" else None
            response = request_fn(url, **kwargs) if request_fn else requests.request(method=method_name, url=url, **kwargs)
            if response.status_code not in retry_statuses:
                _safe_cache_delete(circuit_key)
                return response
            last_exc = requests.HTTPError(f"HTTP {response.status_code}", response=response)
        except requests.RequestException as exc:
            last_exc = exc

        failures = int((_safe_cache_get(circuit_key, {}) or {}).get("failures") or 0) + 1
        next_state = {"failures": failures, "last_failure_at": time.time()}
        if failures >= threshold:
            next_state["open_until"] = time.time() + open_seconds
        _safe_cache_set(circuit_key, next_state, timeout=max(open_seconds * 2, 120))

        if attempt < attempts - 1 and base_backoff:
            time.sleep(base_backoff * (2 ** attempt))

    if isinstance(last_exc, requests.HTTPError) and getattr(last_exc, "response", None) is not None:
        return last_exc.response
    if last_exc is not None:
        raise last_exc
    raise requests.RequestException(f"{source} request failed without a response.")


def retry_quarantined_record(row: SyncQuarantine) -> dict[str, Any]:
    from .integrations import upsert_grants_opportunity, upsert_sam_opportunity, upsert_usaspending_award

    handlers = {
        "opportunity.sam": (upsert_sam_opportunity, "sam.gov"),
        "opportunity.grants": (upsert_grants_opportunity, "grants.gov"),
        "award.usaspending": (upsert_usaspending_award, "usaspending.gov"),
    }
    if row.record_type == "award.usaspending.vehicle":
        from .models import Award
        obj, created = upsert_usaspending_award(dict(row.raw_data or {}), award_type=Award.AwardType.VEHICLE)
        source = "usaspending.gov"
    else:
        handler = handlers.get(row.record_type)
        if handler is None:
            raise ValueError(f"Quarantine type {row.record_type} does not support automatic retry.")
        fn, source = handler
        obj, created = fn(dict(row.raw_data or {}))
    row.resolved_at = timezone.now()
    row.resolution_note = "Reprocessed successfully through the v3.0.8 integrity pipeline."
    row.save(update_fields=["resolved_at", "resolution_note", "updated_at"])
    return {"id": row.id, "source": source, "record_id": getattr(obj, "id", None), "created": created, "resolved": True}


def data_integrity_payload(*, limit: int = 25) -> dict[str, Any]:
    versions = list(
        SourceRecordVersion.objects.values("source", "record_type")
        .annotate(
            versions=Count("id"),
            records=Count("source_id", distinct=True),
            latest_observation=Max("last_seen_at"),
        )
        .order_by("source", "record_type")
    )
    unresolved_qs = SyncQuarantine.objects.filter(resolved_at__isnull=True)
    by_source = list(
        unresolved_qs.values("source", "record_type")
        .annotate(records=Count("id"), occurrences=Sum("occurrences"))
        .order_by("source", "record_type")
    )
    recent = list(
        unresolved_qs.values(
            "id", "source", "record_type", "source_id", "reason", "error_message",
            "occurrences", "created_at", "updated_at",
        )[: max(1, min(int(limit), 100))]
    )
    return {
        "summary": {
            "version_rows": SourceRecordVersion.objects.count(),
            "tracked_records": SourceRecordVersion.objects.values("source", "record_type", "source_id").distinct().count(),
            "unresolved_quarantine": unresolved_qs.count(),
        },
        "versions": versions,
        "quarantine_by_source": by_source,
        "quarantine": recent,
    }
