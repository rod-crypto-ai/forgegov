from __future__ import annotations

from .texas import TexasSmartbuyReferenceConnector
from .usaspending import UsaSpendingAwardConnector


connector_registry = {
    connector.descriptor.key: connector
    for connector in (
        UsaSpendingAwardConnector(),
        TexasSmartbuyReferenceConnector(),
    )
}


def get_connector(key: str):
    return connector_registry.get(key)
