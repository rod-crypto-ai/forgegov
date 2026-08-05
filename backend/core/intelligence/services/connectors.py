from __future__ import annotations

from ..adapters import connector_registry


def connector_health(probe: bool = False) -> dict:
    rows = [adapter.health(probe=probe).to_dict() for adapter in connector_registry]
    healthy = sum(1 for row in rows if row["status"] == "healthy")
    return {
        "connectors": rows,
        "summary": {
            "total": len(rows),
            "healthy": healthy,
            "attention": len(rows) - healthy,
        },
    }
