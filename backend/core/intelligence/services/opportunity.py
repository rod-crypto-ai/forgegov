from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from django.db.models import Q

from ...integrations import fetch_sam_opportunity_detail
from ...models import Award, Opportunity, OrganizationProfile
from ..evidence import derived_evidence, official_evidence
from ..schemas import Confidence, IntelligenceResult


def _decimal(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _candidate_competitors(agency: str, naics: str, psc: str, limit: int = 8) -> list[dict[str, Any]]:
    awards = Award.objects.all()
    if agency:
        awards = awards.filter(Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency))
    if naics:
        awards = awards.filter(Q(naics_code__icontains=naics))
    if psc:
        awards = awards.filter(Q(psc_code__icontains=psc))
    counts: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for row in awards.order_by("-start_date")[:500]:
        name = (getattr(row, "recipient_name", "") or "").strip()
        if not name:
            continue
        counts[name] += 1
        totals[name] += int(_decimal(getattr(row, "obligated_amount", 0)))
    maximum = max(counts.values(), default=1)
    return [
        {
            "name": name,
            "historical_awards": count,
            "historical_value": totals[name],
            "confidence": min(95, 50 + round((count / maximum) * 45)),
            "classification": "ai_derived",
            "reason": "Historical awards overlap this agency, NAICS, or PSC. This is a likely competitor, not an official bidder list.",
        }
        for name, count in counts.most_common(limit)
    ]


def _teaming_matches(naics: str, psc: str, limit: int = 8) -> list[dict[str, Any]]:
    profiles = OrganizationProfile.objects.filter(is_public=True, accepting_partners=True).select_related("organization")
    rows: list[dict[str, Any]] = []
    for profile in profiles[:200]:
        naics_codes = profile.naics_codes or []
        psc_codes = profile.psc_codes or []
        reasons: list[str] = []
        score = 30
        if naics and naics in naics_codes:
            score += 35
            reasons.append(f"NAICS {naics} match")
        if psc and psc in psc_codes:
            score += 25
            reasons.append(f"PSC {psc} match")
        if profile.certifications:
            score += min(10, len(profile.certifications) * 2)
            reasons.append("Published certifications")
        if score <= 30:
            continue
        rows.append({
            "organization_id": profile.organization_id,
            "name": profile.organization.name,
            "score": min(score, 100),
            "reasons": reasons or ["Accepting partners"],
            "classification": "platform",
            "href": f"/network?company={profile.organization_id}",
        })
    return sorted(rows, key=lambda row: row["score"], reverse=True)[:limit]


def opportunity_intelligence(source_id: str, refresh: bool = False) -> dict[str, Any]:
    stored = Opportunity.objects.filter(source_id=source_id).first()
    warnings: list[str] = []
    detail: dict[str, Any] = {}
    try:
        detail = fetch_sam_opportunity_detail(source_id) or {}
    except Exception as exc:
        warnings.append(f"Live SAM.gov detail was unavailable: {exc}")
    title = detail.get("title") or getattr(stored, "title", "") or source_id
    agency = detail.get("department") or detail.get("agency") or getattr(stored, "agency", "") or ""
    naics = str(detail.get("naicsCode") or detail.get("naics") or getattr(stored, "naics_code", "") or "")
    psc = str(detail.get("classificationCode") or detail.get("psc") or getattr(stored, "psc_code", "") or "")
    awards = Award.objects.filter(Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency)).order_by("-start_date")[:25] if agency else Award.objects.none()
    past_winners: list[dict[str, Any]] = []
    seen: set[str] = set()
    for award in awards:
        name = (getattr(award, "recipient_name", "") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        past_winners.append({
            "name": name,
            "award_id": getattr(award, "source_id", "") or str(award.pk),
            "value": _decimal(getattr(award, "obligated_amount", 0)),
            "award_date": getattr(award, "start_date", None),
            "classification": "official",
        })
        if len(past_winners) >= 8:
            break
    incumbent = past_winners[0] if past_winners else None
    evidence = [official_evidence("SAM.gov", "Opportunity notice", f"https://sam.gov/opp/{source_id}/view", "Official solicitation record")]
    if past_winners:
        evidence.append(official_evidence("USAspending / stored awards", "Historical award records", detail="Normalized award history stored by ForgeGov"))
    competitors = _candidate_competitors(agency, naics, psc)
    if competitors:
        evidence.append(derived_evidence("ForgeGov competition engine", "Likely competitor ranking", "Ranks historical award overlap; it is not an official bidder list.", Confidence.MEDIUM))
    teaming = _teaming_matches(naics, psc)
    result = IntelligenceResult(
        subject_id=source_id,
        subject_type="opportunity",
        data={
            "opportunity": {"source_id": source_id, "title": title, "agency": agency, "naics": naics, "psc": psc, "source_url": f"https://sam.gov/opp/{source_id}/view"},
            "incumbent": incumbent,
            "past_winners": past_winners,
            "likely_competitors": competitors,
            "teaming_recommendations": teaming,
            "labels": {"official": "Official government or stored public data", "ai_derived": "Inference—not an official bidder list", "platform": "ForgeGov company-network data"},
        },
        evidence=evidence,
        warnings=warnings,
    )
    return result.to_dict()
