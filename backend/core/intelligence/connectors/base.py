from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(slots=True)
class ConnectorDescriptor:
    key: str
    name: str
    scope: str
    jurisdiction_code: str = ""
    jurisdiction_name: str = ""
    official_url: str = ""
    documentation_url: str = ""
    license_name: str = ""
    license_url: str = ""
    authentication: str = ""
    capabilities: list[str] = field(default_factory=list)
    rate_limit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "scope": self.scope,
            "jurisdiction_code": self.jurisdiction_code,
            "jurisdiction_name": self.jurisdiction_name,
            "official_url": self.official_url,
            "documentation_url": self.documentation_url,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "authentication": self.authentication,
            "capabilities": self.capabilities,
            "rate_limit": self.rate_limit,
        }


class ProcurementConnector(ABC):
    descriptor: ConnectorDescriptor

    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def iter_awards(self, **filters: Any) -> Iterable[dict[str, Any]]:
        return []

    def iter_opportunities(self, **filters: Any) -> Iterable[dict[str, Any]]:
        return []
