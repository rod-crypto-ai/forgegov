from __future__ import annotations

from .texas import TexasSmartbuyReferenceConnector
from .usaspending import UsaSpendingAwardConnector
from .reference import registered_sources


connector_registry = {
    connector.descriptor.key: connector
    for connector in (
        UsaSpendingAwardConnector(),
        TexasSmartbuyReferenceConnector(),
        *registered_sources,
    )
}


def get_connector(key: str):
    return connector_registry.get(key)
