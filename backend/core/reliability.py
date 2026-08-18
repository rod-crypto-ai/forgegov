from __future__ import annotations

from time import perf_counter
from typing import Any, Callable
import uuid

from celery import current_app
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from .models import DataSyncRun
from .version import VERSION


def _timed_check(check: Callable[[], None]) -> dict[str, Any]:
    started = perf_counter()
    try:
        check()
    except Exception as exc:
        return {
            "status": "unavailable",
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "error": type(exc).__name__,
        }
    return {
        "status": "healthy",
        "latency_ms": round((perf_counter() - started) * 1000, 1),
    }


def database_health() -> dict[str, Any]:
    def probe() -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    return _timed_check(probe)


def cache_health() -> dict[str, Any]:
    key = f"forgegov:readiness:{uuid.uuid4().hex}"

    def probe() -> None:
        cache.set(key, "ok", timeout=15)
        if cache.get(key) != "ok":
            raise RuntimeError("cache round-trip failed")
        cache.delete(key)

    return _timed_check(probe)


def celery_health(timeout: float | None = None) -> dict[str, Any]:
    started = perf_counter()
    timeout = float(timeout or getattr(settings, "RELIABILITY_CELERY_PING_TIMEOUT", 1.0))
    try:
        inspector = current_app.control.inspect(timeout=timeout)
        replies = inspector.ping() or {}
        workers = sorted(replies.keys())
        return {
            "status": "healthy" if workers else "degraded",
            "workers": len(workers),
            "worker_names": workers,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "workers": 0,
            "worker_names": [],
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "error": type(exc).__name__,
        }


def sync_freshness() -> dict[str, Any]:
    threshold_hours = int(getattr(settings, "RELIABILITY_SYNC_STALE_HOURS", 30))
    now = timezone.now()
    rows: dict[str, Any] = {}
    sources = tuple(getattr(settings, "RELIABILITY_SYNC_SOURCES", ("sam.gov", "usaspending.gov")))

    for source in sources:
        latest = DataSyncRun.objects.filter(source=source).order_by("-started_at").first()
        if not latest:
            rows[source] = {
                "status": "unknown",
                "latest_run": None,
                "age_hours": None,
                "detail": "No sync run recorded yet.",
            }
            continue

        reference_time = latest.finished_at or latest.started_at
        age_hours = max(0.0, (now - reference_time).total_seconds() / 3600)
        if latest.status == DataSyncRun.Status.FAILED:
            state = "failed"
        elif latest.status == DataSyncRun.Status.PARTIAL:
            state = "partial"
        elif latest.status == DataSyncRun.Status.RUNNING:
            state = "running"
        elif age_hours > threshold_hours:
            state = "stale"
        else:
            state = "fresh"

        rows[source] = {
            "status": state,
            "latest_run": latest.id,
            "run_status": latest.status,
            "started_at": latest.started_at,
            "finished_at": latest.finished_at,
            "age_hours": round(age_hours, 1),
            "records_received": latest.records_received,
            "records_created": latest.records_created,
            "records_updated": latest.records_updated,
        }

    return {"stale_after_hours": threshold_hours, "sources": rows}


def readiness_payload() -> dict[str, Any]:
    checks = {
        "database": database_health(),
        "cache": cache_health(),
    }
    ready = all(row.get("status") == "healthy" for row in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "service": "forgegov-api",
        "product": "ForgeGov",
        "version": VERSION,
        "checks": checks,
    }


def operational_health(*, probe_connectors: bool = True) -> dict[str, Any]:
    from .intelligence.services.connectors import connector_health
    from .integration_resilience import data_integrity_payload

    readiness = readiness_payload()
    try:
        connectors = connector_health(probe=probe_connectors)
    except Exception as exc:
        connectors = {
            "connectors": [],
            "summary": {"total": 0, "healthy": 0, "attention": 0},
            "error": type(exc).__name__,
        }

    return {
        "status": readiness["status"],
        "version": VERSION,
        "critical": readiness["checks"],
        "workers": celery_health(),
        "sync_freshness": sync_freshness(),
        "data_integrity": data_integrity_payload(limit=10),
        "connectors": connectors,
    }
