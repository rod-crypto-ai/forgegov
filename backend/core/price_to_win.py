from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any

from django.db.models import Q

from .models import Award, Opportunity, PriceToWinSnapshot, PricingPlan
from .pricing_engine import calculate_plan, dec, money


HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def _award_value(award: Award) -> Decimal:
    potential = dec(award.potential_amount)
    obligated = dec(award.obligated_amount)
    return potential if potential > 0 else obligated


def _match_score(opportunity: Opportunity, award: Award) -> int:
    score = 0
    agency = (opportunity.agency or "").strip().lower()
    award_agency = (award.awarding_agency or "").strip().lower()
    if agency and award_agency:
        if agency == award_agency:
            score += 45
        elif agency in award_agency or award_agency in agency:
            score += 35

    if opportunity.naics_code and award.naics_code == opportunity.naics_code:
        score += 30
    if opportunity.psc_code and award.psc_code == opportunity.psc_code:
        score += 20

    # Same jurisdiction and contract award types are more comparable.
    if award.jurisdiction_level == "federal":
        score += 3
    if award.award_type in {Award.AwardType.CONTRACT, Award.AwardType.IDV}:
        score += 2
    return min(score, 100)


def _percentile(values: list[Decimal], fraction: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (Decimal(len(ordered) - 1) * fraction)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - Decimal(lower)
    return ordered[lower] * (Decimal("1") - weight) + ordered[upper] * weight


def _escalate(value: Decimal, award: Award, annual_percent: Decimal) -> tuple[Decimal, int]:
    if annual_percent == 0:
        return value, 0
    source_year = None
    if award.start_date:
        source_year = award.start_date.year
    elif award.end_date:
        source_year = award.end_date.year
    if not source_year:
        return value, 0
    years = max(0, min(date.today().year - source_year, 10))
    if not years:
        return value, 0
    factor = (Decimal("1") + annual_percent / HUNDRED) ** years
    return value * factor, years


def _margin_at_price(cost: Decimal, price: Decimal | None) -> Decimal | None:
    if price is None or price <= 0:
        return None
    return ((price - cost) / price * HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def _profit_at_price(cost: Decimal, price: Decimal | None) -> Decimal | None:
    if price is None:
        return None
    return money(price - cost)


def build_price_to_win(*, organization, opportunity: Opportunity) -> dict[str, Any]:
    plan = PricingPlan.objects.filter(
        organization=organization,
        opportunity=opportunity,
    ).prefetch_related("cost_items", "clins", "scenarios").order_by("-revision").first()
    pricing = calculate_plan(plan) if plan else None
    cost = dec(pricing["totals"]["total_cost"]) if pricing else Decimal("0")
    current_bid = dec(pricing["totals"]["price"]) if pricing else None
    annual_escalation = dec(plan.annual_escalation_percent) if plan else Decimal("0")

    awards = Award.objects.filter(
        award_type__in=[Award.AwardType.CONTRACT, Award.AwardType.IDV],
    ).filter(Q(obligated_amount__gt=0) | Q(potential_amount__gt=0))

    filters = Q()
    if opportunity.agency:
        filters |= Q(awarding_agency__icontains=opportunity.agency)
    if opportunity.naics_code:
        filters |= Q(naics_code=opportunity.naics_code)
    if opportunity.psc_code:
        filters |= Q(psc_code=opportunity.psc_code)
    if filters:
        awards = awards.filter(filters)
    else:
        awards = awards.none()

    comparable_rows = []
    for award in awards.order_by("-start_date", "-updated_at")[:250]:
        score = _match_score(opportunity, award)
        if score < 30:
            continue
        raw_value = _award_value(award)
        if raw_value <= 0:
            continue
        adjusted, years = _escalate(raw_value, award, annual_escalation)
        comparable_rows.append({
            "award": award,
            "match_score": score,
            "raw_value": raw_value,
            "adjusted_value": adjusted,
            "escalation_years": years,
        })

    comparable_rows.sort(
        key=lambda row: (row["match_score"], row["award"].start_date or date.min, row["adjusted_value"]),
        reverse=True,
    )
    comparable_rows = comparable_rows[:40]

    # Use stronger comparables preferentially, but permit broader evidence when sparse.
    strong = [row for row in comparable_rows if row["match_score"] >= 65]
    modeled_rows = strong if len(strong) >= 3 else comparable_rows[:20]
    values = [row["adjusted_value"] for row in modeled_rows]

    floor = _percentile(values, Decimal("0.35"))
    target = _percentile(values, Decimal("0.50"))
    ceiling = _percentile(values, Decimal("0.65"))

    # Confidence rewards strong matching, quantity, recency, and price-model readiness.
    evidence_count = len(modeled_rows)
    average_match = (
        sum(row["match_score"] for row in modeled_rows) / evidence_count
        if evidence_count else 0
    )
    quantity_score = min(35, evidence_count * 4)
    match_score = min(40, int(average_match * 0.45))
    recency_count = sum(
        1 for row in modeled_rows
        if row["award"].start_date and row["award"].start_date.year >= date.today().year - 5
    )
    recency_score = min(15, recency_count * 3)
    model_score = 10 if plan and plan.cost_items.exists() else 0
    confidence = min(95, quantity_score + match_score + recency_score + model_score)

    assumptions = []
    warnings = []
    if annual_escalation and any(row["escalation_years"] for row in modeled_rows):
        assumptions.append(
            f"Historical award values were normalized using the pricing plan's {annual_escalation}% annual escalation assumption."
        )
    assumptions.append(
        "Competitive range is a ForgeGov model derived from public historical award values; it is not a competitor bid prediction."
    )
    if len(strong) < 3:
        warnings.append("Fewer than three high-strength comparables were found; the model broadened the evidence set.")
    if evidence_count < 3:
        warnings.append("Insufficient comparable award evidence for a reliable price-to-win range.")
    if confidence < 50:
        warnings.append("Price-to-win confidence is low. Treat the range as directional, not decision-grade.")

    position = "not_modeled"
    if current_bid is not None and floor and target and ceiling:
        if current_bid < floor:
            position = "below_competitive_floor"
        elif current_bid <= target:
            position = "competitive"
        elif current_bid <= ceiling:
            position = "above_target_within_range"
        else:
            position = "above_modeled_range"

    floor_margin = _margin_at_price(cost, floor)
    target_margin = _margin_at_price(cost, target)
    ceiling_margin = _margin_at_price(cost, ceiling)
    minimum_margin = dec(plan.minimum_margin_percent) if plan else Decimal("0")

    viability = {
        "competitive_floor": {
            "price": money(floor) if floor is not None else None,
            "profit": _profit_at_price(cost, floor),
            "margin_percent": floor_margin,
            "clears_margin_floor": floor_margin is not None and floor_margin >= minimum_margin,
        },
        "modeled_target": {
            "price": money(target) if target is not None else None,
            "profit": _profit_at_price(cost, target),
            "margin_percent": target_margin,
            "clears_margin_floor": target_margin is not None and target_margin >= minimum_margin,
        },
        "protective_ceiling": {
            "price": money(ceiling) if ceiling is not None else None,
            "profit": _profit_at_price(cost, ceiling),
            "margin_percent": ceiling_margin,
            "clears_margin_floor": ceiling_margin is not None and ceiling_margin >= minimum_margin,
        },
    }

    if floor_margin is not None and floor_margin < minimum_margin:
        warnings.append(
            f"The modeled competitive floor would produce a {floor_margin}% margin, below the configured {minimum_margin}% minimum."
        )
    if target_margin is not None and target_margin < minimum_margin:
        warnings.append(
            "The modeled target price is financially unattractive under the current cost structure."
        )

    evidence = [{
        "award_id": row["award"].id,
        "source_id": row["award"].source_id,
        "award_number": row["award"].award_number,
        "recipient_name": row["award"].recipient_name,
        "awarding_agency": row["award"].awarding_agency,
        "naics_code": row["award"].naics_code,
        "psc_code": row["award"].psc_code,
        "raw_value": money(row["raw_value"]),
        "adjusted_value": money(row["adjusted_value"]),
        "start_date": row["award"].start_date,
        "end_date": row["award"].end_date,
        "match_score": row["match_score"],
        "source": row["award"].source,
        "source_url": row["award"].source_url,
    } for row in modeled_rows[:12]]

    history = PriceToWinSnapshot.objects.filter(
        organization=organization,
        opportunity=opportunity,
    )[:10]

    return {
        "range": {
            "competitive_floor": money(floor) if floor is not None else None,
            "target": money(target) if target is not None else None,
            "protective_ceiling": money(ceiling) if ceiling is not None else None,
        },
        "confidence": confidence,
        "evidence_count": evidence_count,
        "strong_comparable_count": len(strong),
        "current_pricing": {
            "price": money(current_bid) if current_bid is not None else None,
            "cost": money(cost),
            "margin_percent": pricing["totals"]["margin_percent"] if pricing else None,
            "minimum_margin_percent": plan.minimum_margin_percent if plan else None,
            "revision": plan.revision if plan else None,
            "status": plan.status if plan else "not_started",
            "position": position,
        },
        "viability": viability,
        "evidence": evidence,
        "assumptions": assumptions,
        "warnings": list(dict.fromkeys(warnings)),
        "history": [{
            "id": row.id,
            "created_at": row.created_at,
            "competitive_floor": row.competitive_floor,
            "target_price": row.target_price,
            "protective_ceiling": row.protective_ceiling,
            "confidence": row.confidence,
            "evidence_count": row.evidence_count,
        } for row in history],
        "classification": "derived_from_official_historical_awards",
    }


def record_price_to_win(*, organization, opportunity: Opportunity, user=None) -> PriceToWinSnapshot:
    result = build_price_to_win(organization=organization, opportunity=opportunity)
    plan = PricingPlan.objects.filter(
        organization=organization,
        opportunity=opportunity,
    ).order_by("-revision").first()

    comparable_ids = [row["award_id"] for row in result["evidence"]]
    return PriceToWinSnapshot.objects.create(
        organization=organization,
        opportunity=opportunity,
        pricing_plan=plan,
        competitive_floor=result["range"]["competitive_floor"],
        target_price=result["range"]["target"],
        protective_ceiling=result["range"]["protective_ceiling"],
        confidence=result["confidence"],
        evidence_count=result["evidence_count"],
        comparable_award_ids=comparable_ids,
        assumptions=result["assumptions"],
        warnings=result["warnings"],
        model_inputs={
            "agency": opportunity.agency,
            "naics_code": opportunity.naics_code,
            "psc_code": opportunity.psc_code,
            "pricing_revision": plan.revision if plan else None,
        },
        recorded_by=user,
    )
