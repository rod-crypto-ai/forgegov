from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

DATA_FILE = Path(__file__).resolve().parent / "data" / "naics_2022.json"


@lru_cache(maxsize=1)
def _dataset() -> dict:
    return json.loads(DATA_FILE.read_text())


@api_view(["GET"])
@permission_classes([AllowAny])
def naics_reference(request):
    payload = _dataset()
    query = str(request.query_params.get("q") or "").strip().lower()
    level_raw = str(request.query_params.get("level") or "").strip()
    try:
        limit = max(1, min(int(request.query_params.get("limit") or 50), 250))
    except (TypeError, ValueError):
        limit = 50

    level = None
    if level_raw:
        try:
            level = int(level_raw)
        except ValueError:
            return Response({"detail": "level must be an integer from 2 through 6."}, status=400)
        if level < 2 or level > 6:
            return Response({"detail": "level must be an integer from 2 through 6."}, status=400)

    rows = payload.get("records") or []
    if level is not None:
        rows = [row for row in rows if row.get("level") == level]
    if query:
        rows = [
            row for row in rows
            if query in str(row.get("code") or "").lower()
            or query in str(row.get("title") or "").lower()
        ]

    rows = rows[:limit]
    return Response({
        "version": payload.get("version"),
        "source": payload.get("source"),
        "source_url": payload.get("source_url"),
        "total_reference_records": payload.get("record_count", 0),
        "count": len(rows),
        "results": rows,
    })
