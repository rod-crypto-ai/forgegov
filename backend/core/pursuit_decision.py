from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .capture_intelligence import build_capture_assessment
from .models import PipelineItem, PricingPlan, ProposalCloseout, PursuitDecisionSnapshot
from .pricing_engine import calculate_plan
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

    scores = dict(assessment["scores"])
    pricing_plan = PricingPlan.objects.filter(
        organization=organization,
        opportunity=opportunity,
    ).prefetch_related("cost_items", "clins", "scenarios").order_by("-revision").first()
    pricing_calc = calculate_plan(pricing_plan) if pricing_plan else None
    if pricing_plan and pricing_plan.cost_items.exists():
        margin = _decimal(pricing_calc["totals"]["margin_percent"], Decimal("0")) or Decimal("0")
        minimum = _decimal(pricing_plan.minimum_margin_percent, Decimal("0")) or Decimal("0")
        completeness = min(100, 45 + pricing_plan.cost_items.count() * 6 + pricing_plan.clins.count() * 4)
        margin_score = 100 if margin >= minimum else max(10, int((margin / minimum * 100) if minimum else 50))
        scores["pricing"] = _bounded(completeness * 0.55 + margin_score * 0.45)
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
    if pricing_plan and pricing_calc and pricing_plan.cost_items.exists():
        if _decimal(pricing_calc["totals"]["margin_percent"], Decimal("0")) < _decimal(pricing_plan.minimum_margin_percent, Decimal("0")):
            conditions.append("Target pricing is below the configured minimum margin; reprice or obtain executive approval.")
    elif scores.get("pricing", 0) < 60:
        conditions.append("Establish a defensible cost and margin model before committing proposal resources.")
    if scores.get("compliance", 0) < 55:
        conditions.append("Resolve material compliance uncertainty before bid authorization.")
    if scores.get("schedule", 0) < 40:
        hard_blockers.append("Current schedule risk is too high for a responsible pursuit without executive override.")
    if evidence_coverage < 40:
        conditions.append("Increase evidence coverage; the current decision has too many unknowns.")

    recommendation = _recommendation(decision_score, hard_blockers, conditions)
    win_probability = _bounded(decision_score * 0.72 + int(scores.get("competition", 0)) * 0.12 + int(scores.get("past_performance", 0)) * 0.16, 5, 95)

    pricing_price = _decimal(pricing_calc["totals"]["price"]) if pricing_calc else None
    estimated_value = pricing_price or _decimal(pipeline.estimated_value if pipeline else None)
    expected_value = (estimated_value * Decimal(win_probability) / Decimal("100")) if estimated_value is not None else None
    pricing_margin = _decimal(pricing_calc["totals"]["margin_percent"]) if pricing_calc else None
    pricing_pursuit_cost = _decimal(pricing_plan.pursuit_cost) if pricing_plan else None
    pricing_subcontract_share = None
    if pricing_calc and _decimal(pricing_calc["totals"]["total_cost"], Decimal("0")):
        pricing_subcontract_share = (
            _decimal(pricing_calc["totals"]["subcontract_direct"], Decimal("0"))
            / _decimal(pricing_calc["totals"]["total_cost"], Decimal("1"))
            * Decimal("100")
        )

    evidence = [
        {"label": "Solicitation documents", "classification": "official_or_indexed", "available": scores.get("documents", 0) >= 40, "detail": f"Document score {scores.get('documents', 0)}/100"},
        {"label": "Historical awards", "classification": "official_historical", "available": scores.get("past_performance", 0) >= 55 or bool(win.get("competitors")), "detail": f"Past-performance score {scores.get('past_performance', 0)}/100"},
        {"label": "Pipeline assumptions", "classification": "workspace", "available": bool(pipeline), "detail": "Value and user-entered pursuit data" if pipeline else "Opportunity has not been fully qualified in pipeline"},
        {"label": "Competitive posture", "classification": "derived", "available": True, "detail": f"Competition score {scores.get('competition', 0)}/100; historical inference, not an official bidder list"},
        {"label": "Pricing model", "classification": "workspace_financial", "available": bool(pricing_plan and pricing_plan.cost_items.exists()), "detail": f"Revision {pricing_plan.revision} · {pricing_plan.cost_items.count()} cost items" if pricing_plan else "No ForgeGov pricing model has been created"},
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
            "target_margin_percent": pricing_margin,
            "pursuit_cost": pricing_pursuit_cost,
            "subcontractor_share_percent": pricing_subcontract_share,
            "estimated_delivery_cost": _decimal(pricing_calc["totals"]["total_cost"]) if pricing_calc else None,
            "projected_profit": _decimal(pricing_calc["totals"]["profit"]) if pricing_calc else None,
            "pricing_revision": pricing_plan.revision if pricing_plan else None,
            "pricing_status": pricing_plan.status if pricing_plan else "not_started",
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
