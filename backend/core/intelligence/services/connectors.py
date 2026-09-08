from __future__ import annotations

from .award_ingestion import connector_registry_payload


def connector_health(probe: bool = False) -> dict:
    payload = connector_registry_payload(probe=probe)
    payload["connectors"] = [{**row, "label": row["name"]} for row in payload["connectors"]]
    return payload
