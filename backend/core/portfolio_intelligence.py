from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from .models import PortfolioSnapshot, PricingPlan, ProposalCloseout, Pursuit
from .pricing_engine import calculate_plan, dec, money
from .prime_sub_cashflow import prime_sub_payload

HUNDRED = Decimal("100")


def _stage_weight(stage: str, probability: int) -> Decimal:
    # Shared financial metrics always mean entered value × entered Pwin.
    # Stage assumptions must be shown separately, never silently mixed in.
    return Decimal(probability or 0) / HUNDRED


def build_portfolio_intelligence(*, organization) -> dict[str, Any]:
    pipeline = list(
        Pursuit.objects.filter(organization=organization)
        .exclude(stage__in=[Pursuit.Stage.AWARDED, Pursuit.Stage.LOST, Pursuit.Stage.NO_BID])
        .select_related("opportunity")
        .order_by("-updated_at")
    )
    pricing_plans = {}
    for plan in (
        PricingPlan.objects.filter(organization=organization)
        .prefetch_related("cost_items", "clins", "scenarios", "subcontractors")
        .order_by("opportunity_id", "-revision")
    ):
        pricing_plans.setdefault(plan.opportunity_id, plan)

    pipeline_value = Decimal("0")
    weighted_pipeline = Decimal("0")
    modeled_revenue = Decimal("0")
    modeled_cost = Decimal("0")
    projected_profit = Decimal("0")
    weighted_profit = Decimal("0")
    working_capital = Decimal("0")
    working_capital_gap = Decimal("0")
    option_year_value = Decimal("0")
    active_rows = []
    agency_rollup = defaultdict(lambda: {"pipeline": Decimal("0"), "weighted": Decimal("0"), "count": 0})
    stage_rollup = defaultdict(lambda: {"value": Decimal("0"), "weighted": Decimal("0"), "count": 0})
    risk_counts = defaultdict(int)

    for row in pipeline:
        plan = pricing_plans.get(row.opportunity_id) if row.opportunity_id else None
        calc = calculate_plan(plan) if plan else None
        prime_sub = prime_sub_payload(plan) if plan else None

        value = dec(calc["totals"]["price"]) if calc and dec(calc["totals"]["price"]) > 0 else dec(row.estimated_value)
        cost = dec(calc["totals"]["total_cost"]) if calc else Decimal("0")
        profit = dec(calc["totals"]["profit"]) if calc else Decimal("0")
        margin = dec(calc["totals"]["margin_percent"]) if calc else Decimal("0")
        probability = int(row.probability_of_win or 0)
        weight = _stage_weight(row.stage, probability)
        weighted_value = value * weight
        weighted_row_profit = profit * weight

        pipeline_value += value
        weighted_pipeline += weighted_value
        modeled_revenue += value if plan else Decimal("0")
        modeled_cost += cost
        projected_profit += profit
        weighted_profit += weighted_row_profit

        cash = prime_sub.get("cashflow", {}) if prime_sub else {}
        required_wc = dec(cash.get("recommended_working_capital"))
        wc_gap = dec(cash.get("working_capital_gap"))
        working_capital += required_wc
        working_capital_gap += wc_gap
        wc_risk = str(cash.get("risk") or "not_modeled")
        risk_counts[wc_risk] += 1

        if plan:
            for clin in calc.get("clins", []):
                if int(clin.get("option_year") or 0) > 0:
                    option_year_value += dec(clin.get("target_price"))

        agency = ((row.opportunity.agency if row.opportunity else "") or "Agency unavailable").strip()
        agency_rollup[agency]["pipeline"] += value
        agency_rollup[agency]["weighted"] += weighted_value
        agency_rollup[agency]["count"] += 1

        stage_rollup[row.stage]["value"] += value
        stage_rollup[row.stage]["weighted"] += weighted_value
        stage_rollup[row.stage]["count"] += 1

        active_rows.append({
            "pipeline_id": row.id,
            "pursuit_id": row.id,
            "source_id": row.opportunity.source_id if row.opportunity else "",
            "title": row.title,
            "agency": agency,
            "stage": row.stage,
            "probability_of_win": probability,
            "value": money(value),
            "weighted_value": money(weighted_value),
            "modeled_cost": money(cost) if plan else None,
            "projected_profit": money(profit) if plan else None,
            "margin_percent": money(margin) if plan else None,
            "pricing_revision": plan.revision if plan else None,
            "pricing_status": plan.status if plan else "not_started",
            "working_capital_required": money(required_wc) if prime_sub else None,
            "working_capital_gap": money(wc_gap) if prime_sub else None,
            "working_capital_risk": wc_risk,
        })

    awarded_closeouts = ProposalCloseout.objects.filter(
        plan__organization=organization,
        status=ProposalCloseout.Status.AWARDED,
    ).select_related("plan", "plan__opportunity")
    backlog_value = sum((dec(row.award_value) for row in awarded_closeouts), Decimal("0"))

    portfolio_margin = (projected_profit / modeled_revenue * HUNDRED) if modeled_revenue else Decimal("0")
    weighted_margin = (weighted_profit / weighted_pipeline * HUNDRED) if weighted_pipeline else Decimal("0")

    concentration_rows = []
    for agency, totals in agency_rollup.items():
        share = (totals["pipeline"] / pipeline_value * HUNDRED) if pipeline_value else Decimal("0")
        concentration_rows.append({
            "agency": agency,
            "pipeline_value": money(totals["pipeline"]),
            "weighted_value": money(totals["weighted"]),
            "opportunity_count": totals["count"],
            "share_percent": money(share),
        })
    concentration_rows.sort(key=lambda r: dec(r["pipeline_value"]), reverse=True)

    stage_rows = [{
        "stage": stage,
        "value": money(totals["value"]),
        "weighted_value": money(totals["weighted"]),
        "count": totals["count"],
    } for stage, totals in stage_rollup.items()]
    stage_rows.sort(key=lambda r: dec(r["weighted_value"]), reverse=True)

    risks = []
    if concentration_rows and dec(concentration_rows[0]["share_percent"]) >= Decimal("50"):
        risks.append({
            "severity": "high",
            "title": "Customer concentration",
            "detail": f"{concentration_rows[0]['agency']} represents {concentration_rows[0]['share_percent']}% of active pipeline value.",
        })
    if working_capital_gap > 0:
        risks.append({
            "severity": "high",
            "title": "Portfolio working-capital gap",
            "detail": f"Modeled pursuits require approximately {money(working_capital_gap)} more capital than currently available in their pricing assumptions.",
        })
    if modeled_revenue and portfolio_margin < Decimal("8"):
        risks.append({
            "severity": "high",
            "title": "Low portfolio margin",
            "detail": f"Modeled portfolio margin is {money(portfolio_margin)}%, below a typical internal floor of 8%.",
        })
    if option_year_value and modeled_revenue and option_year_value / modeled_revenue * HUNDRED >= Decimal("35"):
        risks.append({
            "severity": "medium",
            "title": "Option-year dependency",
            "detail": f"{money(option_year_value)} of modeled revenue depends on option-year pricing rather than base-period value.",
        })
    if risk_counts["critical"] or risk_counts["high"]:
        risks.append({
            "severity": "high",
            "title": "Liquidity-heavy pursuits",
            "detail": f"{risk_counts['critical'] + risk_counts['high']} active pursuit(s) have High or Critical working-capital risk.",
        })
    priced_count = sum(1 for row in active_rows if row["pricing_revision"] is not None)
    if active_rows and priced_count < len(active_rows):
        risks.append({
            "severity": "medium",
            "title": "Incomplete financial evidence",
            "detail": f"{len(active_rows) - priced_count} of {len(active_rows)} active pursuit(s) do not have a pricing model; portfolio financial conclusions are incomplete.",
        })
    if not active_rows:
        risks.append({
            "severity": "info",
            "title": "Insufficient portfolio evidence",
            "detail": "Add active pursuits and pricing evidence before drawing portfolio-level financial conclusions.",
        })
    elif not risks:
        risks.append({
            "severity": "success",
            "title": "No modeled portfolio-level financial red flags",
            "detail": "The current priced pursuits do not trigger ForgeGov concentration, margin, or liquidity guardrails.",
        })

    history = PortfolioSnapshot.objects.filter(organization=organization)[:12]

    return {
        "summary": {
            "pipeline_value": money(pipeline_value),
            "weighted_pipeline_value": money(weighted_pipeline),
            "modeled_revenue": money(modeled_revenue),
            "modeled_cost": money(modeled_cost),
            "projected_profit": money(projected_profit),
            "weighted_profit": money(weighted_profit),
            "portfolio_margin_percent": money(portfolio_margin),
            "weighted_margin_percent": money(weighted_margin),
            "backlog_value": money(backlog_value),
            "option_year_value": money(option_year_value),
            "recommended_working_capital": money(working_capital),
            "working_capital_gap": money(working_capital_gap),
            "active_opportunity_count": len(active_rows),
            "priced_opportunity_count": priced_count,
        },
        "opportunities": active_rows,
        "agency_concentration": concentration_rows[:12],
        "stage_distribution": stage_rows,
        "working_capital_risk": dict(risk_counts),
        "risks": risks,
        "history": [{
            "id": row.id,
            "created_at": row.created_at,
            "pipeline_value": row.pipeline_value,
            "weighted_pipeline_value": row.weighted_pipeline_value,
            "modeled_revenue": row.modeled_revenue,
            "projected_profit": row.projected_profit,
            "backlog_value": row.backlog_value,
            "portfolio_margin_percent": row.portfolio_margin_percent,
            "working_capital_gap": row.working_capital_gap,
        } for row in history],
    }


def record_portfolio_snapshot(*, organization, user=None) -> PortfolioSnapshot:
    result = build_portfolio_intelligence(organization=organization)
    summary = result["summary"]
    return PortfolioSnapshot.objects.create(
        organization=organization,
        pipeline_value=summary["pipeline_value"],
        weighted_pipeline_value=summary["weighted_pipeline_value"],
        modeled_revenue=summary["modeled_revenue"],
        projected_profit=summary["projected_profit"],
        backlog_value=summary["backlog_value"],
        recommended_working_capital=summary["recommended_working_capital"],
        working_capital_gap=summary["working_capital_gap"],
        portfolio_margin_percent=summary["portfolio_margin_percent"],
        opportunity_count=summary["active_opportunity_count"],
        risk_summary=result["working_capital_risk"],
        agency_concentration=[
            {
                **row,
                "pipeline_value": str(row["pipeline_value"]),
                "weighted_value": str(row["weighted_value"]),
                "share_percent": str(row["share_percent"]),
            }
            for row in result["agency_concentration"]
        ],
        recorded_by=user,
    )
