from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class SourceKind(StrEnum):
    OFFICIAL = "official"
    PLATFORM = "platform"
    USER = "user"
    AI_DERIVED = "ai_derived"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Evidence:
    source: str
    source_kind: SourceKind
    title: str
    url: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: Confidence = Confidence.HIGH
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_kind"] = self.source_kind.value
        value["confidence"] = self.confidence.value
        return value


@dataclass(slots=True)
class IntelligenceResult:
    subject_id: str
    subject_type: str
    data: dict[str, Any]
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "data": self.data,
            "evidence": [row.to_dict() for row in self.evidence],
            "warnings": self.warnings,
            "generated_at": self.generated_at,
        }
