from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import (
    Opportunity,
    PricingClin,
    PricingCostItem,
    PricingPlan,
    PricingProfile,
    PricingScenario,
)


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def pct_amount(base: Decimal, percent: Decimal) -> Decimal:
    return base * percent / ONE_HUNDRED


def ensure_pricing_profile(organization, user=None) -> PricingProfile:
    profile, _ = PricingProfile.objects.get_or_create(organization=organization)
    if user and not profile.updated_by_id:
        profile.updated_by = user
        profile.save(update_fields=["updated_by", "updated_at"])
    return profile


def ensure_pricing_plan(*, organization, opportunity: Opportunity, user=None) -> PricingPlan:
    plan = PricingPlan.objects.filter(organization=organization, opportunity=opportunity).order_by("-revision").first()
    if plan:
        ensure_default_scenarios(plan)
        return plan

    profile = ensure_pricing_profile(organization, user)
    plan = PricingPlan.objects.create(
        organization=organization,
        opportunity=opportunity,
        revision=1,
        fringe_percent=profile.fringe_percent,
        overhead_percent=profile.overhead_percent,
        ga_percent=profile.ga_percent,
        material_handling_percent=profile.material_handling_percent,
        subcontract_handling_percent=profile.subcontract_handling_percent,
        payroll_burden_percent=profile.payroll_burden_percent,
        target_profit_percent=profile.default_profit_percent,
        minimum_margin_percent=profile.minimum_margin_percent,
        annual_escalation_percent=profile.annual_escalation_percent,
        created_by=user,
    )
    ensure_default_scenarios(plan)
    return plan


def ensure_default_scenarios(plan: PricingPlan) -> None:
    defaults = {
        PricingScenario.ScenarioType.COMPETITIVE: {
            "profit_percent": max(ZERO, plan.target_profit_percent - Decimal("3")),
            "cost_adjustment_percent": Decimal("-1"),
            "price_adjustment_percent": ZERO,
        },
        PricingScenario.ScenarioType.TARGET: {
            "profit_percent": plan.target_profit_percent,
            "cost_adjustment_percent": ZERO,
            "price_adjustment_percent": ZERO,
        },
        PricingScenario.ScenarioType.PROTECTIVE: {
            "profit_percent": plan.target_profit_percent + Decimal("4"),
            "cost_adjustment_percent": Decimal("3"),
            "price_adjustment_percent": ZERO,
        },
    }
    for scenario_type, values in defaults.items():
        PricingScenario.objects.get_or_create(plan=plan, scenario_type=scenario_type, defaults=values)


def raw_direct(item: PricingCostItem) -> Decimal:
    if item.category == PricingCostItem.Category.LABOR:
        base = dec(item.labor_hours) * dec(item.labor_rate)
    else:
        base = dec(item.quantity, Decimal("1")) * dec(item.unit_cost)
    escalation = dec(item.escalation_percent)
    if not escalation and item.option_year:
        escalation = dec(item.plan.annual_escalation_percent) * Decimal(item.option_year)
    return base + pct_amount(base, escalation)


def item_cost_components(item: PricingCostItem, plan: PricingPlan) -> dict[str, Decimal]:
    direct = raw_direct(item)
    payroll = fringe = overhead = material_handling = subcontract_handling = ZERO

    if item.category == PricingCostItem.Category.LABOR:
        payroll = pct_amount(direct, dec(plan.payroll_burden_percent))
        fringe = pct_amount(direct, dec(plan.fringe_percent))
        overhead = pct_amount(direct + payroll + fringe, dec(plan.overhead_percent))
    elif item.category == PricingCostItem.Category.MATERIAL:
        material_handling = pct_amount(direct, dec(plan.material_handling_percent))
    elif item.category == PricingCostItem.Category.SUBCONTRACT:
        subcontract_handling = pct_amount(direct, dec(plan.subcontract_handling_percent))

    subtotal_before_ga = direct + payroll + fringe + overhead + material_handling + subcontract_handling
    ga = pct_amount(subtotal_before_ga, dec(plan.ga_percent))
    total_cost = subtotal_before_ga + ga

    return {
        "direct": money(direct),
        "payroll_burden": money(payroll),
        "fringe": money(fringe),
        "overhead": money(overhead),
        "material_handling": money(material_handling),
        "subcontract_handling": money(subcontract_handling),
        "ga": money(ga),
        "total_cost": money(total_cost),
    }


def calculate_plan(plan: PricingPlan) -> dict[str, Any]:
    items = list(plan.cost_items.select_related("clin").all())
    totals = {
        "direct": ZERO,
        "labor_direct": ZERO,
        "material_direct": ZERO,
        "travel_direct": ZERO,
        "equipment_direct": ZERO,
        "subcontract_direct": ZERO,
        "other_direct": ZERO,
        "payroll_burden": ZERO,
        "fringe": ZERO,
        "overhead": ZERO,
        "material_handling": ZERO,
        "subcontract_handling": ZERO,
        "ga": ZERO,
        "total_cost": ZERO,
    }
    item_rows = []
    clin_costs: dict[int | None, Decimal] = {}

    for item in items:
        components = item_cost_components(item, plan)
        totals["direct"] += components["direct"]
        totals["payroll_burden"] += components["payroll_burden"]
        totals["fringe"] += components["fringe"]
        totals["overhead"] += components["overhead"]
        totals["material_handling"] += components["material_handling"]
        totals["subcontract_handling"] += components["subcontract_handling"]
        totals["ga"] += components["ga"]
        totals["total_cost"] += components["total_cost"]

        category_key = {
            PricingCostItem.Category.LABOR: "labor_direct",
            PricingCostItem.Category.MATERIAL: "material_direct",
            PricingCostItem.Category.TRAVEL: "travel_direct",
            PricingCostItem.Category.EQUIPMENT: "equipment_direct",
            PricingCostItem.Category.SUBCONTRACT: "subcontract_direct",
        }.get(item.category, "other_direct")
        totals[category_key] += components["direct"]
        clin_costs[item.clin_id] = clin_costs.get(item.clin_id, ZERO) + components["total_cost"]

        item_rows.append({
            "id": item.id,
            "category": item.category,
            "name": item.name,
            "clin_id": item.clin_id,
            "clin": item.clin.clin if item.clin else "",
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "labor_hours": item.labor_hours,
            "labor_rate": item.labor_rate,
            "option_year": item.option_year,
            "escalation_percent": item.escalation_percent,
            "source": item.source,
            "source_kind": item.source_kind,
            "notes": item.notes,
            **components,
        })

    base_cost = totals["total_cost"]
    target_profit = pct_amount(base_cost, dec(plan.target_profit_percent))
    target_price = base_cost + target_profit
    target_margin = (target_profit / target_price * ONE_HUNDRED) if target_price else ZERO
    markup = (target_profit / base_cost * ONE_HUNDRED) if base_cost else ZERO

    scenario_rows = []
    for scenario in plan.scenarios.all():
        scenario_cost = base_cost + pct_amount(base_cost, dec(scenario.cost_adjustment_percent))
        scenario_profit = pct_amount(scenario_cost, dec(scenario.profit_percent))
        scenario_price = scenario_cost + scenario_profit
        scenario_price += pct_amount(scenario_price, dec(scenario.price_adjustment_percent))
        profit = scenario_price - scenario_cost
        margin = profit / scenario_price * ONE_HUNDRED if scenario_price else ZERO
        scenario_rows.append({
            "id": scenario.id,
            "scenario_type": scenario.scenario_type,
            "profit_percent": scenario.profit_percent,
            "cost_adjustment_percent": scenario.cost_adjustment_percent,
            "price_adjustment_percent": scenario.price_adjustment_percent,
            "cost": money(scenario_cost),
            "price": money(scenario_price),
            "profit": money(profit),
            "margin_percent": money(margin),
            "notes": scenario.notes,
        })

    clin_rows = []
    target_multiplier = (target_price / base_cost) if base_cost else Decimal("1")
    for clin in plan.clins.all():
        cost = clin_costs.get(clin.id, ZERO)
        clin_rows.append({
            "id": clin.id,
            "clin": clin.clin,
            "description": clin.description,
            "option_year": clin.option_year,
            "quantity": clin.quantity,
            "unit": clin.unit,
            "cost": money(cost),
            "target_price": money(cost * target_multiplier),
        })

    for key, value in list(totals.items()):
        totals[key] = money(value)

    return {
        "totals": {
            **totals,
            "profit": money(target_profit),
            "price": money(target_price),
            "margin_percent": money(target_margin),
            "markup_percent": money(markup),
            "pursuit_cost": money(dec(plan.pursuit_cost)),
        },
        "items": item_rows,
        "clins": clin_rows,
        "scenarios": scenario_rows,
    }


def pricing_payload(plan: PricingPlan) -> dict[str, Any]:
    calc = calculate_plan(plan)
    return {
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "revision": plan.revision,
            "status": plan.status,
            "fringe_percent": plan.fringe_percent,
            "overhead_percent": plan.overhead_percent,
            "ga_percent": plan.ga_percent,
            "material_handling_percent": plan.material_handling_percent,
            "subcontract_handling_percent": plan.subcontract_handling_percent,
            "payroll_burden_percent": plan.payroll_burden_percent,
            "target_profit_percent": plan.target_profit_percent,
            "minimum_margin_percent": plan.minimum_margin_percent,
            "annual_escalation_percent": plan.annual_escalation_percent,
            "pursuit_cost": plan.pursuit_cost,
            "notes": plan.notes,
            "approved_at": plan.approved_at,
            "updated_at": plan.updated_at,
        },
        **calc,
        "guardrails": pricing_guardrails(plan, calc),
    }


def pricing_guardrails(plan: PricingPlan, calc: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    totals = calc["totals"]
    margin = dec(totals["margin_percent"])
    if margin < dec(plan.minimum_margin_percent):
        rows.append({"severity": "critical", "title": "Margin below floor", "detail": f"Projected margin {margin}% is below the {plan.minimum_margin_percent}% minimum."})
    subcontract = dec(totals["subcontract_direct"])
    total_cost = dec(totals["total_cost"])
    share = subcontract / total_cost * ONE_HUNDRED if total_cost else ZERO
    if share >= Decimal("60"):
        rows.append({"severity": "warning", "title": "High subcontract dependence", "detail": f"Subcontract cost is approximately {money(share)}% of delivery cost."})
    if not plan.cost_items.exists():
        rows.append({"severity": "info", "title": "Pricing model is empty", "detail": "Add labor, materials, travel, equipment, or subcontract costs to build the estimate."})
    if not rows:
        rows.append({"severity": "success", "title": "Economics within current guardrails", "detail": "The target scenario clears the configured minimum margin."})
    return rows


EDITABLE_PLAN_FIELDS = {
    "name", "status", "fringe_percent", "overhead_percent", "ga_percent",
    "material_handling_percent", "subcontract_handling_percent", "payroll_burden_percent",
    "target_profit_percent", "minimum_margin_percent", "annual_escalation_percent",
    "pursuit_cost", "notes",
}


@transaction.atomic
def mutate_pricing_plan(*, plan: PricingPlan, payload: dict[str, Any], user=None) -> PricingPlan:
    action = str(payload.get("action") or "update_plan")

    if plan.status == PricingPlan.Status.LOCKED and action not in {"new_revision"}:
        raise ValueError("This pricing revision is locked. Create a new revision before changing it.")

    if action == "update_plan":
        for field in EDITABLE_PLAN_FIELDS:
            if field in payload:
                setattr(plan, field, payload[field])
        if payload.get("status") == PricingPlan.Status.APPROVED:
            plan.approved_at = timezone.now()
            plan.approved_by = user
        plan.save()
        return plan

    if action == "add_item":
        PricingCostItem.objects.create(
            plan=plan,
            category=str(payload.get("category") or PricingCostItem.Category.OTHER),
            name=str(payload.get("name") or "Cost item")[:500],
            clin_id=payload.get("clin_id") or None,
            quantity=dec(payload.get("quantity"), Decimal("1")),
            unit_cost=dec(payload.get("unit_cost")),
            labor_hours=dec(payload.get("labor_hours")),
            labor_rate=dec(payload.get("labor_rate")),
            option_year=max(0, int(payload.get("option_year") or 0)),
            escalation_percent=dec(payload.get("escalation_percent")),
            source=str(payload.get("source") or "")[:500],
            source_kind=str(payload.get("source_kind") or "user")[:40],
            notes=str(payload.get("notes") or ""),
        )
        return plan

    if action == "update_item":
        item = plan.cost_items.get(pk=int(payload["id"]))
        for field in ("category", "name", "quantity", "unit_cost", "labor_hours", "labor_rate", "option_year", "escalation_percent", "source", "source_kind", "notes"):
            if field in payload:
                setattr(item, field, payload[field])
        if "clin_id" in payload:
            item.clin_id = payload.get("clin_id") or None
        item.save()
        return plan

    if action == "delete_item":
        plan.cost_items.filter(pk=int(payload["id"])).delete()
        return plan

    if action == "add_clin":
        PricingClin.objects.create(
            plan=plan,
            clin=str(payload.get("clin") or "CLIN")[:80],
            description=str(payload.get("description") or "")[:500],
            option_year=max(0, int(payload.get("option_year") or 0)),
            quantity=dec(payload.get("quantity"), Decimal("1")),
            unit=str(payload.get("unit") or "LOT")[:80],
        )
        return plan

    if action == "delete_clin":
        plan.clins.filter(pk=int(payload["id"])).delete()
        return plan

    if action == "update_scenario":
        scenario = plan.scenarios.get(pk=int(payload["id"]))
        for field in ("profit_percent", "cost_adjustment_percent", "price_adjustment_percent", "notes"):
            if field in payload:
                setattr(scenario, field, payload[field])
        scenario.save()
        return plan

    if action == "new_revision":
        plan.status = PricingPlan.Status.LOCKED
        plan.save(update_fields=["status", "updated_at"])
        new_plan = PricingPlan.objects.create(
            organization=plan.organization,
            opportunity=plan.opportunity,
            name=plan.name,
            revision=plan.revision + 1,
            status=PricingPlan.Status.DRAFT,
            fringe_percent=plan.fringe_percent,
            overhead_percent=plan.overhead_percent,
            ga_percent=plan.ga_percent,
            material_handling_percent=plan.material_handling_percent,
            subcontract_handling_percent=plan.subcontract_handling_percent,
            payroll_burden_percent=plan.payroll_burden_percent,
            target_profit_percent=plan.target_profit_percent,
            minimum_margin_percent=plan.minimum_margin_percent,
            annual_escalation_percent=plan.annual_escalation_percent,
            pursuit_cost=plan.pursuit_cost,
            notes=plan.notes,
            created_by=user,
        )
        clin_map = {}
        for clin in plan.clins.all():
            clone = PricingClin.objects.create(
                plan=new_plan, clin=clin.clin, description=clin.description,
                option_year=clin.option_year, quantity=clin.quantity, unit=clin.unit,
                sort_order=clin.sort_order,
            )
            clin_map[clin.id] = clone
        for item in plan.cost_items.all():
            PricingCostItem.objects.create(
                plan=new_plan,
                clin=clin_map.get(item.clin_id),
                category=item.category,
                name=item.name,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                labor_hours=item.labor_hours,
                labor_rate=item.labor_rate,
                option_year=item.option_year,
                escalation_percent=item.escalation_percent,
                source=item.source,
                source_kind=item.source_kind,
                notes=item.notes,
                sort_order=item.sort_order,
            )
        for scenario in plan.scenarios.all():
            PricingScenario.objects.create(
                plan=new_plan, scenario_type=scenario.scenario_type,
                profit_percent=scenario.profit_percent,
                cost_adjustment_percent=scenario.cost_adjustment_percent,
                price_adjustment_percent=scenario.price_adjustment_percent,
                notes=scenario.notes,
            )
        return new_plan

    raise ValueError("Unsupported pricing action.")
