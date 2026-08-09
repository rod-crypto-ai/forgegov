from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .capture_intelligence import build_capture_assessment
from .models import PipelineItem, ProposalCloseout, PursuitDecisionSnapshot
from .win_strategy import build_win_strategy


def _decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _bounded(value: float | int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(float(value))))


def _recommendation(score: int, hard_blockers: list[str], conditions: list[str]) -> str:
    if hard_blockers or score < 45:
        return "NO-BID"
    if score < 60:
        return "HOLD"
    if conditions or score < 76:
        return "PURSUE WITH CONDITIONS"
    return "PURSUE"


def build_pursuit_decision(*, organization, opportunity) -> dict[str, Any]:
    assessment = build_capture_assessment(organization=organization, opportunity=opportunity, include_ai=False)
    win = build_win_strategy(organization=organization, opportunity=opportunity)
    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at").first()

    scores = assessment["scores"]
    weights = {
        "capability": 20,
        "past_performance": 14,
        "competition": 12,
        "compliance": 14,
        "documents": 10,
        "schedule": 8,
        "pricing": 12,
        "proposal_readiness": 10,
    }
    weighted_rows = []
    weighted_total = 0.0
    for key, weight in weights.items():
        score = int(scores.get(key, 0))
        contribution = score * weight / 100
        weighted_total += contribution
        weighted_rows.append({"key": key, "score": score, "weight": weight, "contribution": round(contribution, 1)})

    decision_score = _bounded(weighted_total)
    evidence_coverage = int(assessment["bid_decision"].get("evidence_coverage", 0))
    confidence = _bounded(40 + evidence_coverage * 0.55, 40, 95)

    conditions: list[str] = []
    hard_blockers: list[str] = []
    if scores.get("capability", 0) < 55:
        conditions.append("Close the documented capability gap or secure a qualified teaming partner.")
    if scores.get("past_performance", 0) < 55:
        conditions.append("Validate relevant past performance or add a partner with directly relevant performance.")
    if scores.get("pricing", 0) < 60:
        conditions.append("Establish a defensible price-to-win and cost basis before committing proposal resources.")
    if scores.get("compliance", 0) < 55:
        conditions.append("Resolve material compliance uncertainty before bid authorization.")
    if scores.get("schedule", 0) < 40:
        hard_blockers.append("Current schedule risk is too high for a responsible pursuit without executive override.")
    if evidence_coverage < 40:
        conditions.append("Increase evidence coverage; the current decision has too many unknowns.")

    recommendation = _recommendation(decision_score, hard_blockers, conditions)
    win_probability = _bounded(decision_score * 0.72 + int(scores.get("competition", 0)) * 0.12 + int(scores.get("past_performance", 0)) * 0.16, 5, 95)

    estimated_value = _decimal(pipeline.estimated_value if pipeline else None)
    expected_value = (estimated_value * Decimal(win_probability) / Decimal("100")) if estimated_value is not None else None

    evidence = [
        {"label": "Solicitation documents", "classification": "official_or_indexed", "available": scores.get("documents", 0) >= 40, "detail": f"Document score {scores.get('documents', 0)}/100"},
        {"label": "Historical awards", "classification": "official_historical", "available": scores.get("past_performance", 0) >= 55 or bool(win.get("competitors")), "detail": f"Past-performance score {scores.get('past_performance', 0)}/100"},
        {"label": "Pipeline assumptions", "classification": "workspace", "available": bool(pipeline), "detail": "Value and user-entered pursuit data" if pipeline else "Opportunity has not been fully qualified in pipeline"},
        {"label": "Competitive posture", "classification": "derived", "available": True, "detail": f"Competition score {scores.get('competition', 0)}/100; historical inference, not an official bidder list"},
    ]

    history = PursuitDecisionSnapshot.objects.filter(organization=organization, opportunity=opportunity)[:12]
    closeouts = ProposalCloseout.objects.filter(plan__organization=organization).exclude(win_loss_reason="").order_by("-updated_at")[:5]
    feedback = [{"status": row.status, "reason": row.win_loss_reason, "lessons_learned": row.lessons_learned} for row in closeouts]

    return {
        "decision": {
            "recommendation": recommendation,
            "score": decision_score,
            "win_probability": win_probability,
            "confidence": confidence,
            "evidence_coverage": evidence_coverage,
            "hard_blockers": hard_blockers,
            "conditions": conditions,
        },
        "scorecard": weighted_rows,
        "economics": {
            "estimated_value": estimated_value,
            "expected_value": expected_value,
            "target_margin_percent": None,
            "pursuit_cost": None,
            "subcontractor_share_percent": None,
        },
        "competitive_position": {
            "incumbent": win.get("incumbent", {}),
            "competitors": win.get("competitors", [])[:6],
            "teaming_gaps": win.get("teaming_recommendations", [])[:6],
            "strengths": win.get("win_strategy", {}).get("strengths", []),
            "gaps": win.get("win_strategy", {}).get("gaps", []),
        },
        "evidence": evidence,
        "rationale": assessment["bid_decision"].get("rationale", []),
        "history": [{
            "id": row.id, "created_at": row.created_at, "recommendation": row.recommendation,
            "win_probability": row.win_probability, "confidence": row.confidence,
            "evidence_coverage": row.evidence_coverage, "expected_value": row.expected_value,
        } for row in history],
        "learning_feedback": feedback,
        "warning": "Probability of win is an explainable ForgeGov decision-support estimate, not a factual prediction or guarantee.",
    }


def record_pursuit_decision(*, organization, opportunity, user, payload: dict[str, Any]) -> PursuitDecisionSnapshot:
    result = build_pursuit_decision(organization=organization, opportunity=opportunity)
    economics = result["economics"]
    for key in ("target_margin_percent", "pursuit_cost", "subcontractor_share_percent"):
        if key in payload:
            economics[key] = _decimal(payload.get(key))
    if payload.get("estimated_value") not in (None, ""):
        economics["estimated_value"] = _decimal(payload.get("estimated_value"))
        economics["expected_value"] = economics["estimated_value"] * Decimal(result["decision"]["win_probability"]) / Decimal("100")
    return PursuitDecisionSnapshot.objects.create(
        organization=organization,
        opportunity=opportunity,
        recommendation=result["decision"]["recommendation"],
        win_probability=result["decision"]["win_probability"],
        confidence=result["decision"]["confidence"],
        evidence_coverage=result["decision"]["evidence_coverage"],
        estimated_value=economics["estimated_value"],
        expected_value=economics["expected_value"],
        target_margin_percent=economics["target_margin_percent"],
        pursuit_cost=economics["pursuit_cost"],
        subcontractor_share_percent=economics["subcontractor_share_percent"],
        scorecard=result["scorecard"],
        evidence=result["evidence"],
        conditions=result["decision"]["conditions"],
        rationale=result["rationale"],
        recorded_by=user,
    )
