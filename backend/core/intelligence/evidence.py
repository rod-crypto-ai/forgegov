from __future__ import annotations

from typing import Any

from .schemas import Confidence, Evidence, SourceKind


def official_evidence(source: str, title: str, url: str = "", detail: str = "") -> Evidence:
    return Evidence(
        source=source,
        source_kind=SourceKind.OFFICIAL,
        title=title,
        url=url,
        confidence=Confidence.HIGH,
        detail=detail,
    )


def derived_evidence(source: str, title: str, detail: str, confidence: Confidence = Confidence.MEDIUM) -> Evidence:
    return Evidence(
        source=source,
        source_kind=SourceKind.AI_DERIVED,
        title=title,
        confidence=confidence,
        detail=detail,
    )


def attach_evidence(payload: dict[str, Any], evidence: Evidence) -> dict[str, Any]:
    return {**payload, "evidence": evidence.to_dict()}
