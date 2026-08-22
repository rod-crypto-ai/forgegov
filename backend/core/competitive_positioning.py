from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from datetime import date, datetime
from typing import Any

from django.db.models import Q
from django.utils import timezone

from .capture_intelligence import build_capture_assessment
from .models import Award, CompetitivePositionSnapshot, OrganizationProfile, PipelineItem
from .win_strategy import build_win_strategy


def _money(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _bounded(value: float | int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(float(value))))


def _normalized(value: str) -> str:
    return " ".join(str(value or "").upper().split())


def _json_safe(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _award_payload(row: Award) -> dict[str, Any]:
    return {
        "award_id": row.source_id,
        "award_number": row.award_number,
        "recipient_name": row.recipient_name,
        "recipient_uei": row.recipient_uei,
        "agency": row.awarding_agency or row.funding_agency,
        "office": row.awarding_office or row.funding_office,
        "obligated_amount": _money(row.obligated_amount),
        "potential_amount": _money(row.potential_amount),
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "naics": row.naics_code,
        "psc": row.psc_code,
        "set_aside_code": row.set_aside_code,
        "place_of_performance": row.place_of_performance,
        "source_url": row.source_url,
        "classification": "official_historical_award",
    }


def _agency_awards(opportunity, limit: int = 1200) -> list[Award]:
    agency = str(opportunity.agency or "").strip()
    if not agency:
        return []
    tokens = [part.strip() for part in agency.replace(" > ", "|").split("|") if len(part.strip()) >= 4]
    query = Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency)
    for token in tokens[:4]:
        query |= Q(awarding_agency__icontains=token) | Q(funding_agency__icontains=token)
    return list(
        Award.objects.filter(jurisdiction_level="federal").filter(query).order_by("-end_date", "-start_date", "-updated_at")[:limit]
    )


def _agency_profile(opportunity, awards: list[Award]) -> dict[str, Any]:
    if not awards:
        return {
            "agency": opportunity.agency,
            "award_count": 0,
            "vendor_count": 0,
            "obligated_amount": 0.0,
            "repeat_vendor_share": 0,
            "top_vendors": [],
            "common_naics": [],
            "common_psc": [],
            "recent_awards": [],
            "classification": "official_evidence_missing",
            "warning": "No stored federal award history matched this agency. Refresh USAspending history before relying on agency buying patterns.",
        }

    vendor = defaultdict(lambda: {"count": 0, "value": 0.0, "uei": ""})
    naics = Counter()
    psc = Counter()
    total = 0.0
    for row in awards:
        name = str(row.recipient_name or "").strip()
        if name:
            item = vendor[_normalized(name)]
            item["name"] = name
            item["count"] += 1
            item["value"] += _money(row.obligated_amount)
            item["uei"] = item["uei"] or row.recipient_uei
        if row.naics_code:
            naics[row.naics_code] += 1
        if row.psc_code:
            psc[row.psc_code] += 1
        total += _money(row.obligated_amount)

    ranked_vendors = sorted(vendor.values(), key=lambda item: (item["value"], item["count"]), reverse=True)
    repeat_awards = sum(item["count"] for item in vendor.values() if item["count"] > 1)
    return {
        "agency": opportunity.agency,
        "award_count": len(awards),
        "vendor_count": len(vendor),
        "obligated_amount": total,
        "average_obligated_amount": total / len(awards) if awards else 0.0,
        "repeat_vendor_share": _bounded(repeat_awards / len(awards) * 100 if awards else 0),
        "top_vendors": [
            {
                "name": item["name"],
                "uei": item["uei"],
                "award_count": item["count"],
                "obligated_amount": item["value"],
                "share_of_obligations": round(item["value"] / total * 100, 1) if total else 0.0,
                "classification": "official_historical_award_rollup",
            }
            for item in ranked_vendors[:10]
        ],
        "common_naics": [{"code": code, "award_count": count} for code, count in naics.most_common(8)],
        "common_psc": [{"code": code, "award_count": count} for code, count in psc.most_common(8)],
        "recent_awards": [_award_payload(row) for row in awards[:10]],
        "classification": "official_historical_award_rollup",
        "warning": "Agency buying history summarizes stored official award records; it does not predict a future award decision.",
    }


def _competitor_profiles(opportunity, competitors: list[dict[str, Any]], agency_awards: list[Award]) -> list[dict[str, Any]]:
    agency_total = sum(_money(row.obligated_amount) for row in agency_awards)
    agency_by_vendor = defaultdict(lambda: {"count": 0, "value": 0.0})
    for award in agency_awards:
        name = _normalized(award.recipient_name)
        if not name:
            continue
        agency_by_vendor[name]["count"] += 1
        agency_by_vendor[name]["value"] += _money(award.obligated_amount)

    profiles: list[dict[str, Any]] = []
    for candidate in competitors[:8]:
        name = str(candidate.get("name") or "").strip()
        if not name:
            continue
        rows = list(Award.objects.filter(jurisdiction_level="federal", recipient_name__iexact=name).order_by("-end_date", "-start_date", "-updated_at")[:500])
        total = sum(_money(row.obligated_amount) for row in rows)
        agencies = Counter(str(row.awarding_agency or row.funding_agency or "").strip() for row in rows if row.awarding_agency or row.funding_agency)
        naics = Counter(row.naics_code for row in rows if row.naics_code)
        psc = Counter(row.psc_code for row in rows if row.psc_code)
        agency_stats = agency_by_vendor[_normalized(name)]

        signals = []
        if agency_stats["count"]:
            signals.append(f"{agency_stats['count']} stored award(s) with this customer/agency")
        if opportunity.naics_code and naics.get(opportunity.naics_code):
            signals.append(f"{naics[opportunity.naics_code]} stored award(s) in NAICS {opportunity.naics_code}")
        if opportunity.psc_code and psc.get(opportunity.psc_code):
            signals.append(f"{psc[opportunity.psc_code]} stored award(s) in PSC {opportunity.psc_code}")
        if rows:
            signals.append(f"{len(rows)} stored federal award record(s) in ForgeGov")

        questions = [
            "Validate whether this company is actively pursuing the opportunity; historical awards do not prove bidder intent.",
            "Compare confirmed contract vehicle, certification, staffing, and place-of-performance requirements before treating this company as a direct threat.",
        ]
        if not agency_stats["count"]:
            questions.append("No stored award with this agency was found for this vendor; verify customer-specific past performance before black-hat conclusions.")

        profiles.append({
            "name": name,
            "uei": candidate.get("uei") or (rows[0].recipient_uei if rows else ""),
            "confidence": candidate.get("confidence", 0),
            "classification": "competitive_profile_from_official_awards",
            "historical_award_count": len(rows),
            "historical_obligated_amount": total,
            "agency_award_count": agency_stats["count"],
            "agency_obligated_amount": agency_stats["value"],
            "agency_obligation_share": round(agency_stats["value"] / agency_total * 100, 1) if agency_total else 0.0,
            "common_agencies": [{"name": key, "award_count": value} for key, value in agencies.most_common(5)],
            "common_naics": [{"code": key, "award_count": value} for key, value in naics.most_common(5)],
            "common_psc": [{"code": key, "award_count": value} for key, value in psc.most_common(5)],
            "latest_award": _award_payload(rows[0]) if rows else None,
            "known_signals": signals,
            "questions_to_validate": questions,
            "warning": "Competitive profile is derived from historical award evidence and is not an official bidder list or a statement of current intent.",
        })
    return profiles


def _company_fit(organization, opportunity) -> dict[str, Any]:
    profile = OrganizationProfile.objects.filter(organization=organization).first()
    if not profile:
        return {
            "score": 35,
            "signals": [],
            "gaps": ["Company profile is incomplete; add NAICS, PSC, capabilities, certifications, and service areas before relying on fit scoring."],
        }
    signals: list[str] = []
    gaps: list[str] = []
    score = 35
    naics = {str(value) for value in (profile.naics_codes or [])}
    pscs = {str(value) for value in (profile.psc_codes or [])}
    if opportunity.naics_code:
        if opportunity.naics_code in naics:
            score += 25
            signals.append(f"Company profile covers NAICS {opportunity.naics_code}.")
        else:
            gaps.append(f"Company profile does not list NAICS {opportunity.naics_code}.")
    if opportunity.psc_code:
        if opportunity.psc_code in pscs:
            score += 15
            signals.append(f"Company profile covers PSC {opportunity.psc_code}.")
        else:
            gaps.append(f"Company profile does not list PSC {opportunity.psc_code}.")
    if profile.capabilities:
        score += min(15, len(profile.capabilities) * 3)
        signals.append(f"{len(profile.capabilities)} capability statement item(s) are available for validation against the solicitation.")
    if profile.certifications:
        score += min(10, len(profile.certifications) * 2)
        signals.append(f"{len(profile.certifications)} certification(s) are recorded; only use those explicitly relevant to the requirement.")
    return {"score": _bounded(score), "signals": signals, "gaps": gaps}


def _qualification(organization, opportunity, assessment: dict[str, Any], win: dict[str, Any], agency_profile: dict[str, Any]) -> dict[str, Any]:
    fit = _company_fit(organization, opportunity)
    evidence = int(assessment.get("bid_decision", {}).get("evidence_coverage") or 0)
    readiness = int(assessment.get("scores", {}).get("proposal_readiness") or 0)
    competition_count = len(win.get("competitors") or [])
    competition = 85 if competition_count <= 2 else 72 if competition_count <= 5 else 58 if competition_count <= 8 else 42
    agency_evidence = 85 if agency_profile.get("award_count", 0) >= 20 else 70 if agency_profile.get("award_count", 0) >= 5 else 45 if agency_profile.get("award_count") else 25
    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at").first()
    execution = 70 if pipeline else 40
    if pipeline and pipeline.owner_id:
        execution += 10
    if pipeline and pipeline.next_action:
        execution += 10
    execution = _bounded(execution)

    factors = [
        {"key": "company_fit", "label": "Company fit", "score": fit["score"], "weight": 25, "detail": "; ".join(fit["signals"][:2]) or "Company-profile evidence is limited."},
        {"key": "evidence", "label": "Evidence coverage", "score": evidence, "weight": 20, "detail": f"Capture evidence coverage is {evidence}%."},
        {"key": "proposal_readiness", "label": "Proposal readiness", "score": readiness, "weight": 20, "detail": f"Proposal readiness is {readiness}/100."},
        {"key": "competitive_position", "label": "Competitive position", "score": competition, "weight": 15, "detail": f"{competition_count} likely competitor signal(s) are currently inferred."},
        {"key": "agency_history", "label": "Agency intelligence", "score": agency_evidence, "weight": 10, "detail": f"{agency_profile.get('award_count', 0)} stored agency award record(s) support market analysis."},
        {"key": "capture_execution", "label": "Capture execution", "score": execution, "weight": 10, "detail": "Pipeline ownership and next-action discipline improve execution readiness." if pipeline else "Opportunity is not yet established in the company pipeline."},
    ]
    score = _bounded(sum(row["score"] * row["weight"] for row in factors) / 100)
    blockers = list(fit["gaps"])
    blockers.extend(str(row.get("requirement")) for row in win.get("compliance_matrix", []) if row.get("status") == "missing")
    if evidence < 45:
        blockers.append("Capture evidence coverage is below 45%; validate solicitation documents and customer requirements before committing resources.")
    recommendation = "qualified" if score >= 75 and not blockers else "conditional" if score >= 55 else "hold"
    return {
        "score": score,
        "recommendation": recommendation,
        "factors": factors,
        "conditions": blockers[:8],
        "warning": "Qualification score is an explainable decision-support model, not a guaranteed win probability or an instruction to bid.",
    }


def _win_themes(organization, opportunity, win: dict[str, Any], qualification: dict[str, Any]) -> list[dict[str, Any]]:
    profile = OrganizationProfile.objects.filter(organization=organization).first()
    themes: list[dict[str, Any]] = []

    strengths = list(win.get("win_strategy", {}).get("strengths") or [])
    hypotheses = list(win.get("win_strategy", {}).get("customer_evaluation_hypotheses") or [])
    if strengths:
        themes.append({
            "title": "Prove direct requirement fit",
            "message": "Lead with company evidence that directly maps to solicitation scope, NAICS/PSC, and mandatory requirements.",
            "proof_points": strengths[:4],
            "customer_basis": hypotheses[:2],
            "status": "evidence_backed",
            "classification": "forgegov_capture_hypothesis",
        })
    if profile and profile.certifications:
        themes.append({
            "title": "Turn validated certifications into lower execution risk",
            "message": "Use only certifications that map to explicit solicitation or customer requirements; connect each claim to a measurable delivery or compliance benefit.",
            "proof_points": [str(item) for item in profile.certifications[:5]],
            "customer_basis": hypotheses[:2],
            "status": "validate_against_solicitation",
            "classification": "forgegov_capture_hypothesis",
        })
    if win.get("teaming_recommendations"):
        names = [str(row.get("name") or "") for row in win["teaming_recommendations"][:4] if row.get("name")]
        themes.append({
            "title": "Close gaps with an intentional team",
            "message": "Use teaming only where a partner closes a verified capability, certification, geographic, or past-performance gap.",
            "proof_points": names,
            "customer_basis": qualification.get("conditions", [])[:3],
            "status": "requires_partner_validation",
            "classification": "forgegov_capture_hypothesis",
        })
    if not themes:
        themes.append({
            "title": "Do not manufacture a win theme yet",
            "message": "ForgeGov does not have enough validated company/customer evidence to support a differentiated win theme. Close qualification and Section M evidence first.",
            "proof_points": [],
            "customer_basis": hypotheses[:2],
            "status": "insufficient_evidence",
            "classification": "evidence_guardrail",
        })
    return themes[:5]


def build_competitive_positioning(*, organization, opportunity, assessment: dict[str, Any] | None = None, win: dict[str, Any] | None = None) -> dict[str, Any]:
    assessment = assessment or build_capture_assessment(organization=organization, opportunity=opportunity, include_ai=False)
    win = win or build_win_strategy(organization=organization, opportunity=opportunity)
    agency_awards = _agency_awards(opportunity)
    agency = _agency_profile(opportunity, agency_awards)
    competitors = _competitor_profiles(opportunity, win.get("competitors") or [], agency_awards)
    qualification = _qualification(organization, opportunity, assessment, win, agency)
    themes = _win_themes(organization, opportunity, win, qualification)

    incumbent = win.get("incumbent") or {}
    history = CompetitivePositionSnapshot.objects.filter(organization=organization, opportunity=opportunity).order_by("-created_at")[:8]
    return {
        "generated_at": timezone.now().isoformat(),
        "opportunity": {
            "source_id": opportunity.source_id,
            "title": opportunity.title,
            "agency": opportunity.agency,
            "office": opportunity.office,
            "naics": opportunity.naics_code,
            "psc": opportunity.psc_code,
            "set_aside": opportunity.set_aside,
            "response_deadline": opportunity.response_deadline,
        },
        "qualification": qualification,
        "agency_buying_history": agency,
        "incumbent": incumbent,
        "competitor_profiles": competitors,
        "win_themes": themes,
        "black_hat": [
            {
                "competitor": row["name"],
                "confidence": row["confidence"],
                "known_signals": row["known_signals"],
                "questions_to_validate": row["questions_to_validate"],
                "classification": row["classification"],
            }
            for row in competitors[:6]
        ],
        "capture_gaps": list(win.get("win_strategy", {}).get("gaps") or []) + qualification.get("conditions", []),
        "history": [
            {
                "id": row.id,
                "qualification_score": row.qualification_score,
                "recommendation": row.recommendation,
                "competitor_count": len(row.competitors or []),
                "created_at": row.created_at,
                "recorded_by": row.recorded_by.get_full_name() or row.recorded_by.email if row.recorded_by else "System",
            }
            for row in history
        ],
        "labels": {
            "official_historical_award": "Official historical award",
            "official_historical_award_rollup": "Rollup of official historical awards",
            "competitive_profile_from_official_awards": "Competitive profile derived from official award history",
            "forgegov_capture_hypothesis": "ForgeGov capture hypothesis requiring validation",
        },
        "warnings": [
            "Incumbent and competitor identification is inferred from historical public award evidence and is not an official bidder list unless explicitly confirmed by an official source.",
            "Historical award share is not market share for the current procurement and does not prove bidder intent.",
            "Win themes are hypotheses and must be validated against solicitation evaluation criteria, customer intelligence, and company proof points.",
        ],
    }


def record_competitive_positioning(*, organization, opportunity, user) -> CompetitivePositionSnapshot:
    result = build_competitive_positioning(organization=organization, opportunity=opportunity)
    return CompetitivePositionSnapshot.objects.create(
        organization=organization,
        opportunity=opportunity,
        qualification_score=result["qualification"]["score"],
        recommendation=result["qualification"]["recommendation"],
        agency_profile=_json_safe(result["agency_buying_history"]),
        incumbent=_json_safe(result["incumbent"]),
        competitors=_json_safe(result["competitor_profiles"]),
        win_themes=_json_safe(result["win_themes"]),
        capture_gaps=_json_safe(result["capture_gaps"]),
        evidence=_json_safe({"labels": result["labels"], "warnings": result["warnings"]}),
        recorded_by=user,
    )
