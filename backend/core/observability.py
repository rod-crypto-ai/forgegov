from __future__ import annotations

import json
import logging
import re
from time import perf_counter
import uuid


_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{18,}\b"),
    re.compile(r"\bre_[A-Za-z0-9_-]{18,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?([^\s,'\"}]{8,})"),
)


def redact(value):
    if not isinstance(value, str):
        return value
    text = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class RedactSecretsFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = redact(record.msg)
            if isinstance(record.args, dict):
                record.args = {key: redact(value) for key, value in record.args.items()}
            elif record.args:
                record.args = tuple(redact(value) for value in record.args)
        except Exception:
            pass
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for name in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, default=str, separators=(",", ":"))


class RequestTelemetryMiddleware:
    logger = logging.getLogger("forgegov.request")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = str(request.headers.get("X-Request-ID") or "")[:128]
        request_id = supplied if re.fullmatch(r"[A-Za-z0-9._:-]+", supplied) else uuid.uuid4().hex
        request.request_id = request_id
        started = perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            self.logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "duration_ms": round((perf_counter() - started) * 1000, 1),
                },
            )
            raise

        response["X-Request-ID"] = request_id
        self.logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 1),
            },
        )
        return response
