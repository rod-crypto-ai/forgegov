from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ConnectorHealth:
    key: str
    label: str
    configured: bool
    reachable: bool | None
    status: str
    detail: str
    official_url: str
    authentication: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "configured": self.configured,
            "reachable": self.reachable,
            "status": self.status,
            "detail": self.detail,
            "official_url": self.official_url,
            "authentication": self.authentication,
        }


class IntelligenceAdapter(ABC):
    key: str
    label: str

    @abstractmethod
    def health(self, probe: bool = False) -> ConnectorHealth:
        raise NotImplementedError
