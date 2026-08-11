from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import PricingPlan, PricingSubcontractor
from .pricing_engine import calculate_plan, dec, money, pct_amount

HUNDRED = Decimal("100")
THIRTY = Decimal("30")


def subcontractor_row(sub: PricingSubcontractor) -> dict[str, Any]:
    quoted = dec(sub.quoted_cost)
    markup = pct_amount(quoted, dec(sub.prime_markup_percent))
    prime_revenue = quoted + markup
    burden = dec(sub.management_burden) + dec(sub.insurance_cost) + dec(sub.contingency)
    contribution = markup - burden
    effective_margin = (contribution / prime_revenue * HUNDRED) if prime_revenue else Decimal("0")
    deposit = pct_amount(quoted, dec(sub.deposit_percent))
    monthly_burn = dec(sub.monthly_burn)
    if monthly_burn <= 0:
        monthly_burn = quoted / Decimal("12") if quoted else Decimal("0")
    return {
        "id": sub.id,
        "name": sub.name,
        "quoted_cost": money(quoted),
        "prime_markup_percent": sub.prime_markup_percent,
        "prime_revenue": money(prime_revenue),
        "management_burden": money(dec(sub.management_burden)),
        "insurance_cost": money(dec(sub.insurance_cost)),
        "contingency": money(dec(sub.contingency)),
        "net_contribution": money(contribution),
        "effective_margin_percent": money(effective_margin),
        "deposit_percent": sub.deposit_percent,
        "deposit_required": money(deposit),
        "payment_terms_days": sub.payment_terms_days,
        "monthly_burn": money(monthly_burn),
        "source": sub.source,
        "notes": sub.notes,
    }


def cashflow_payload(plan: PricingPlan) -> dict[str, Any]:
    pricing = calculate_plan(plan)
    total_cost = dec(pricing["totals"]["total_cost"])
    months = max(Decimal("1"), dec(plan.performance_months, Decimal("12")))
    monthly_delivery_burn = total_cost / months
    lag_days = max(0, int(plan.payment_lag_days or 0))
    delivery_lag_exposure = monthly_delivery_burn / THIRTY * Decimal(lag_days)

    subs = [subcontractor_row(sub) for sub in plan.subcontractors.all()]
    deposits = sum((dec(row["deposit_required"]) for row in subs), Decimal("0"))

    # Estimate timing mismatch when subs are paid before government reimbursement.
    subcontract_timing_exposure = Decimal("0")
    for row in subs:
        days_gap = max(0, lag_days - int(row["payment_terms_days"] or 0))
        subcontract_timing_exposure += dec(row["monthly_burn"]) / THIRTY * Decimal(days_gap)

    mobilization = dec(plan.mobilization_cost)
    recommended = delivery_lag_exposure + deposits + subcontract_timing_exposure + mobilization
    available = dec(plan.available_working_capital)
    gap = max(Decimal("0"), recommended - available)
    coverage = (available / recommended * HUNDRED) if recommended > 0 else Decimal("100")

    if recommended <= 0:
        risk = "not_modeled"
    elif coverage >= 125:
        risk = "low"
    elif coverage >= 90:
        risk = "moderate"
    elif coverage >= 60:
        risk = "high"
    else:
        risk = "critical"

    warnings: list[str] = []
    if gap > 0:
        warnings.append(f"Available working capital is short by {money(gap)} under the current timing assumptions.")
    if deposits > 0:
        warnings.append(f"Subcontractor deposits require approximately {money(deposits)} before normal reimbursement.")
    if lag_days >= 45:
        warnings.append("Government payment lag assumption is 45 days or more; validate billing and acceptance timing.")
    if risk in {"high", "critical"}:
        warnings.append("Winning at the current economics could create material liquidity pressure during performance.")

    return {
        "performance_months": plan.performance_months,
        "payment_lag_days": lag_days,
        "mobilization_cost": money(mobilization),
        "available_working_capital": money(available),
        "monthly_delivery_burn": money(monthly_delivery_burn),
        "delivery_lag_exposure": money(delivery_lag_exposure),
        "subcontract_deposits": money(deposits),
        "subcontract_timing_exposure": money(subcontract_timing_exposure),
        "recommended_working_capital": money(recommended),
        "working_capital_gap": money(gap),
        "coverage_percent": money(coverage),
        "risk": risk,
        "warnings": warnings,
        "subcontractors": subs,
    }


def prime_sub_payload(plan: PricingPlan) -> dict[str, Any]:
    rows = [subcontractor_row(sub) for sub in plan.subcontractors.all()]
    total_quote = sum((dec(row["quoted_cost"]) for row in rows), Decimal("0"))
    total_prime_revenue = sum((dec(row["prime_revenue"]) for row in rows), Decimal("0"))
    total_contribution = sum((dec(row["net_contribution"]) for row in rows), Decimal("0"))
    effective_margin = (total_contribution / total_prime_revenue * HUNDRED) if total_prime_revenue else Decimal("0")
    return {
        "subcontractors": rows,
        "totals": {
            "quoted_cost": money(total_quote),
            "prime_revenue": money(total_prime_revenue),
            "net_contribution": money(total_contribution),
            "effective_margin_percent": money(effective_margin),
        },
        "cashflow": cashflow_payload(plan),
    }


def mutate_prime_sub(plan: PricingPlan, payload: dict[str, Any]) -> PricingPlan:
    action = str(payload.get("action") or "")
    if plan.status == PricingPlan.Status.LOCKED:
        raise ValueError("This pricing revision is locked. Create a new revision before changing subcontractor economics.")

    if action == "add_subcontractor":
        PricingSubcontractor.objects.create(
            plan=plan,
            name=str(payload.get("name") or "Subcontractor")[:500],
            quoted_cost=dec(payload.get("quoted_cost")),
            prime_markup_percent=dec(payload.get("prime_markup_percent")),
            management_burden=dec(payload.get("management_burden")),
            insurance_cost=dec(payload.get("insurance_cost")),
            contingency=dec(payload.get("contingency")),
            deposit_percent=dec(payload.get("deposit_percent")),
            payment_terms_days=max(0, int(payload.get("payment_terms_days") or 30)),
            monthly_burn=dec(payload.get("monthly_burn")),
            source=str(payload.get("source") or "")[:500],
            notes=str(payload.get("notes") or ""),
        )
        return plan

    if action == "update_subcontractor":
        sub = plan.subcontractors.get(pk=int(payload["id"]))
        for field in (
            "name", "quoted_cost", "prime_markup_percent", "management_burden",
            "insurance_cost", "contingency", "deposit_percent", "payment_terms_days",
            "monthly_burn", "source", "notes",
        ):
            if field in payload:
                setattr(sub, field, payload[field])
        sub.save()
        return plan

    if action == "delete_subcontractor":
        plan.subcontractors.filter(pk=int(payload["id"])).delete()
        return plan

    if action == "update_cashflow":
        for field in (
            "performance_months", "payment_lag_days", "mobilization_cost",
            "available_working_capital",
        ):
            if field in payload:
                setattr(plan, field, payload[field])
        plan.save()
        return plan

    raise ValueError("Unsupported prime/sub or cash-flow action.")
