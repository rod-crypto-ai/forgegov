from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import timezone

from .document_intelligence import capture_readiness_summary
from .models import Award, NetworkConnection, OpportunityDocument, OrganizationProfile, PipelineItem


def _money(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _bounded(value: float | int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(float(value))))


def _tokens(value: str) -> set[str]:
    stop = {"this", "that", "with", "from", "into", "shall", "will", "support", "services", "service", "contract", "requirement", "requirements"}
    return {word.strip(".,:;()[]{}").lower() for word in str(value or "").split() if len(word.strip(".,:;()[]{}")) >= 5 and word.lower() not in stop}


def _opportunity_award_score(opportunity, award: Award) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if opportunity.naics_code and award.naics_code == opportunity.naics_code:
        score += 32
        reasons.append(f"NAICS {opportunity.naics_code} match")
    if opportunity.psc_code and award.psc_code == opportunity.psc_code:
        score += 30
        reasons.append(f"PSC {opportunity.psc_code} match")
    agency = (opportunity.agency or "").strip().lower()
    award_agencies = f"{award.awarding_agency} {award.funding_agency}".lower()
    if agency and (agency in award_agencies or any(part in award_agencies for part in agency.split(" > ") if len(part) > 5)):
        score += 22
        reasons.append("Agency overlap")
    title_tokens = _tokens(opportunity.title)
    award_tokens = _tokens(award.description)
    overlap = sorted(title_tokens & award_tokens)
    if overlap:
        score += min(16, len(overlap) * 4)
        reasons.append("Scope terms: " + ", ".join(overlap[:4]))
    return _bounded(score), reasons


def _award_candidates(opportunity, limit: int = 400) -> list[tuple[Award, int, list[str]]]:
    query = Q()
    if opportunity.naics_code:
        query |= Q(naics_code=opportunity.naics_code)
    if opportunity.psc_code:
        query |= Q(psc_code=opportunity.psc_code)
    if opportunity.agency:
        query |= Q(awarding_agency__icontains=opportunity.agency) | Q(funding_agency__icontains=opportunity.agency)
    awards = Award.objects.filter(jurisdiction_level="federal")
    if query:
        awards = awards.filter(query)
    scored: list[tuple[Award, int, list[str]]] = []
    for award in awards.order_by("-end_date", "-start_date", "-updated_at")[:limit]:
        score, reasons = _opportunity_award_score(opportunity, award)
        if score >= 22:
            scored.append((award, score, reasons))
    scored.sort(key=lambda row: (row[1], row[0].end_date or row[0].start_date or timezone.now().date(), _money(row[0].obligated_amount)), reverse=True)
    return scored


def _similar_contracts(opportunity) -> list[dict[str, Any]]:
    rows = []
    for award, score, reasons in _award_candidates(opportunity)[:12]:
        rows.append({
            "award_id": award.source_id,
            "award_number": award.award_number,
            "recipient_name": award.recipient_name,
            "recipient_uei": award.recipient_uei,
            "agency": award.awarding_agency or award.funding_agency,
            "obligated_amount": _money(award.obligated_amount),
            "potential_amount": _money(award.potential_amount),
            "start_date": award.start_date,
            "end_date": award.end_date,
            "naics": award.naics_code,
            "psc": award.psc_code,
            "place_of_performance": award.place_of_performance,
            "source_url": award.source_url,
            "match_score": score,
            "match_reasons": reasons,
            "classification": "official_historical_award",
        })
    return rows


def _incumbent_signal(similar: list[dict[str, Any]]) -> dict[str, Any]:
    if not similar:
        return {
            "status": "not_found",
            "classification": "official_evidence_missing",
            "confidence": 0,
            "reason": "No sufficiently similar stored federal award was found. Synchronize more USAspending history or verify the predecessor contract manually.",
        }
    # Prefer a high-similarity award whose performance end date is recent/current.
    ranked = sorted(
        similar,
        key=lambda row: (
            row["match_score"],
            str(row.get("end_date") or ""),
            row["obligated_amount"],
        ),
        reverse=True,
    )
    best = ranked[0]
    confidence = _bounded(45 + best["match_score"] * 0.5, 45, 94)
    return {
        **best,
        "status": "likely",
        "confidence": confidence,
        "classification": "derived_from_official_awards",
        "reason": "Strongest predecessor/incumbent signal among similar official historical awards. Verify the predecessor contract before treating this as confirmed.",
    }


def _competitors(similar: list[dict[str, Any]], incumbent_name: str = "") -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"awards": 0, "value": 0.0, "best_match": 0, "latest_end": None, "uei": ""})
    for row in similar:
        name = str(row.get("recipient_name") or "").strip()
        if not name:
            continue
        item = grouped[name]
        item["awards"] += 1
        item["value"] += float(row.get("obligated_amount") or 0)
        item["best_match"] = max(item["best_match"], int(row.get("match_score") or 0))
        item["uei"] = item["uei"] or str(row.get("recipient_uei") or "")
        end = row.get("end_date")
        if end and (not item["latest_end"] or str(end) > str(item["latest_end"])):
            item["latest_end"] = end
    rows = []
    max_awards = max((item["awards"] for item in grouped.values()), default=1)
    for name, item in grouped.items():
        if incumbent_name and name.lower() == incumbent_name.lower():
            continue
        confidence = _bounded(42 + item["best_match"] * 0.35 + (item["awards"] / max_awards) * 20, 40, 94)
        rows.append({
            "name": name,
            "uei": item["uei"],
            "historical_awards": item["awards"],
            "historical_obligated": item["value"],
            "best_match_score": item["best_match"],
            "latest_end": item["latest_end"],
            "confidence": confidence,
            "classification": "inferred_competitor",
            "reason": "Ranked from similar official historical awards. This is not an official bidder list.",
        })
    rows.sort(key=lambda row: (row["confidence"], row["historical_awards"], row["historical_obligated"]), reverse=True)
    return rows[:10]


def _structured_document_rows(documents) -> list[tuple[OpportunityDocument, dict[str, Any]]]:
    rows = []
    for document in documents:
        structured = (document.metadata or {}).get("structured_intelligence") or {}
        if structured:
            rows.append((document, structured))
    return rows


def _compliance_matrix(documents) -> list[dict[str, Any]]:
    structured = _structured_document_rows(documents)
    matrix: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(key: str, requirement: str, source: str, category: str, status: str = "needs_review", evidence: str = ""):
        normalized = f"{category}:{requirement}".lower()
        if normalized in seen:
            return
        seen.add(normalized)
        matrix.append({"key": key, "requirement": requirement, "category": category, "source": source, "status": status, "owner": "Unassigned", "evidence": evidence})

    for document, row in structured:
        source = document.file_name
        if row.get("section_l_detected"):
            add(f"section-l-{document.id}", "Review Section L / submission instructions", source, "submission", "needs_review", "Section L indicator detected")
        if row.get("section_m_detected"):
            add(f"section-m-{document.id}", "Review Section M / evaluation factors", source, "evaluation", "needs_review", "Section M indicator detected")
        for clause in (row.get("clauses") or [])[:30]:
            add(f"clause-{len(matrix)}", str(clause), source, "clause", "needs_review", "FAR/DFARS reference extracted from indexed text")
        for certification in [*(row.get("certifications") or []), *(row.get("cmmc") or [])][:20]:
            add(f"cert-{len(matrix)}", str(certification), source, "security_certification", "needs_review", "Certification/security signal extracted from indexed text")
        for deliverable in (row.get("deliverables") or [])[:20]:
            add(f"deliverable-{len(matrix)}", str(deliverable), source, "deliverable", "needs_review", "Deliverable signal extracted from indexed text")
    if not matrix:
        matrix.append({"key": "documents-missing", "requirement": "Index solicitation documents before generating a compliance matrix", "category": "evidence", "source": "ForgeGov", "status": "missing", "owner": "Unassigned", "evidence": "No structured document requirements are currently available."})
    return matrix[:80]


def _required_signals(documents) -> dict[str, set[str]]:
    certs: set[str] = set()
    terms: set[str] = set()
    for _, row in _structured_document_rows(documents):
        certs.update(str(item).strip() for item in [*(row.get("certifications") or []), *(row.get("cmmc") or [])] if str(item).strip())
        terms.update(_tokens(" ".join(str(item) for item in (row.get("labor_categories") or []))))
        terms.update(_tokens(" ".join(str(item) for item in (row.get("deliverables") or []))))
    return {"certifications": certs, "terms": terms}


def _teaming_matches(organization, opportunity, documents) -> list[dict[str, Any]]:
    required = _required_signals(documents)
    profiles = OrganizationProfile.objects.select_related("organization").filter(is_public=True, accepting_partners=True).exclude(organization=organization)[:500]
    connection_map: dict[int, str] = {}
    for connection in NetworkConnection.objects.filter(Q(requester=organization) | Q(recipient=organization)):
        other_id = connection.recipient_id if connection.requester_id == organization.id else connection.requester_id
        connection_map[other_id] = connection.status
    rows = []
    for profile in profiles:
        score = 12
        reasons: list[str] = []
        if opportunity.naics_code and opportunity.naics_code in {str(item) for item in (profile.naics_codes or [])}:
            score += 34
            reasons.append(f"NAICS {opportunity.naics_code} match")
        if opportunity.psc_code and opportunity.psc_code in {str(item) for item in (profile.psc_codes or [])}:
            score += 24
            reasons.append(f"PSC {opportunity.psc_code} match")
        profile_certs = {str(item).lower() for item in (profile.certifications or [])}
        matched_certs = sorted(item for item in required["certifications"] if item.lower() in profile_certs)
        if matched_certs:
            score += min(18, 6 * len(matched_certs))
            reasons.append("Certification overlap: " + ", ".join(matched_certs[:3]))
        capability_text = " ".join([*(profile.capabilities or []), profile.description or "", profile.tagline or ""]).lower()
        term_overlap = sorted(term for term in required["terms"] if term in capability_text)
        if term_overlap:
            score += min(12, len(term_overlap) * 3)
            reasons.append("Capability overlap: " + ", ".join(term_overlap[:4]))
        if profile.verified:
            score += 4
            reasons.append("Verified ForgeGov profile")
        connection_status = connection_map.get(profile.organization_id, "none")
        if connection_status == NetworkConnection.Status.ACCEPTED:
            score += 8
            reasons.append("Existing ForgeGov partnership")
        if score < 28:
            continue
        rows.append({
            "organization_id": profile.organization_id,
            "name": profile.organization.name,
            "score": _bounded(score),
            "reasons": reasons or ["Public ForgeGov teaming profile"],
            "certifications": profile.certifications or [],
            "naics_codes": profile.naics_codes or [],
            "psc_codes": profile.psc_codes or [],
            "state": profile.state,
            "verified": profile.verified,
            "connection_status": connection_status,
            "href": f"/network?company={profile.organization_id}",
            "classification": "forgegov_network_match",
        })
    rows.sort(key=lambda row: (row["score"], row["verified"]), reverse=True)
    return rows[:12]


def _pricing_readiness(pipeline, documents, similar: list[dict[str, Any]]) -> dict[str, Any]:
    readiness = capture_readiness_summary(documents)
    structured = _structured_document_rows(documents)
    clins = {str(item) for _, row in structured for item in (row.get("clins") or [])}
    labor = {str(item) for _, row in structured for item in (row.get("labor_categories") or [])}
    deliverables = {str(item) for _, row in structured for item in (row.get("deliverables") or [])}
    checks = [
        ("estimated_value", bool(pipeline and pipeline.estimated_value), "Pipeline estimated value recorded"),
        ("clins", bool(clins), f"{len(clins)} CLIN/SUBCLIN/ELIN signal(s) extracted"),
        ("labor", bool(labor), f"{len(labor)} labor/staffing signal(s) extracted"),
        ("deliverables", bool(deliverables), f"{len(deliverables)} deliverable signal(s) extracted"),
        ("documents", readiness.get("score", 0) >= 50, f"Document evidence readiness {readiness.get('score', 0)}%"),
        ("benchmarks", bool(similar), f"{len(similar)} similar historical award(s) available for benchmarking"),
    ]
    score = _bounded(sum(1 for _, ok, _ in checks if ok) / len(checks) * 100)
    return {
        "score": score,
        "status": "ready" if score >= 75 else "developing" if score >= 45 else "insufficient_evidence",
        "checks": [{"key": key, "complete": ok, "detail": detail} for key, ok, detail in checks],
        "warning": "ForgeGov does not fabricate a bid price. This score measures whether evidence exists to build a pricing model.",
    }


def build_win_strategy(*, organization, opportunity) -> dict[str, Any]:
    documents = list(OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).prefetch_related("chunks"))
    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at").first()
    similar = _similar_contracts(opportunity)
    incumbent = _incumbent_signal(similar)
    incumbent_name = str(incumbent.get("recipient_name") or "")
    competitors = _competitors(similar, incumbent_name)
    teaming = _teaming_matches(organization, opportunity, documents)
    compliance = _compliance_matrix(documents)
    pricing = _pricing_readiness(pipeline, documents, similar)

    strengths: list[str] = []
    gaps: list[str] = []
    discriminators: list[str] = []
    profile = OrganizationProfile.objects.filter(organization=organization).first()
    profile_naics = {str(item) for item in (profile.naics_codes or [])} if profile else set()
    profile_pscs = {str(item) for item in (profile.psc_codes or [])} if profile else set()
    if opportunity.naics_code and opportunity.naics_code in profile_naics:
        strengths.append(f"Company profile explicitly covers NAICS {opportunity.naics_code}.")
    elif opportunity.naics_code:
        gaps.append(f"Company profile does not list NAICS {opportunity.naics_code}; validate capability/eligibility before bid commitment.")
    if opportunity.psc_code and opportunity.psc_code in profile_pscs:
        strengths.append(f"Company profile explicitly covers PSC {opportunity.psc_code}.")
    if similar:
        strengths.append(f"ForgeGov has {len(similar)} similar official historical award records available for market benchmarking.")
    else:
        gaps.append("Historical award evidence is thin; refresh USAspending data and predecessor research.")
    if compliance and all(row["status"] != "missing" for row in compliance):
        strengths.append("Indexed documents provide an initial compliance evidence base.")
    else:
        gaps.append("Compliance evidence is incomplete; ingest and review all solicitation attachments.")
    if teaming:
        discriminators.append(f"ForgeGov identified {len(teaming)} potential network partner(s) that can close capability or certification gaps.")
    if profile and profile.certifications:
        discriminators.append("Use verified certifications only where they map directly to stated solicitation requirements.")
    if not strengths:
        strengths.append("No strong differentiator is yet supported by stored evidence; treat the pursuit as qualification-stage.")

    evaluation_hypotheses = []
    if documents:
        matrix_categories = {row["category"] for row in compliance}
        if "evaluation" in matrix_categories:
            evaluation_hypotheses.append("Section M/evaluation evidence exists; use it as the primary basis for win themes.")
        if "security_certification" in matrix_categories:
            evaluation_hypotheses.append("Security/certification requirements may be a discriminator or gate; validate exact mandatory language.")
    if not evaluation_hypotheses:
        evaluation_hypotheses.append("Customer/evaluation priorities are not yet sufficiently evidenced. Do not invent win themes until Section M, Q&A, or customer intelligence supports them.")

    actions = []
    if incumbent.get("status") == "likely":
        actions.append({"priority": "high", "title": "Verify predecessor and incumbent", "reason": incumbent["reason"], "href": opportunity.source_url or ""})
    else:
        actions.append({"priority": "high", "title": "Research predecessor contract", "reason": incumbent["reason"], "href": ""})
    if competitors:
        actions.append({"priority": "medium", "title": "Run competitor black-hat review", "reason": f"{len(competitors)} likely competitors were inferred from similar historical awards.", "href": ""})
    if any(row["status"] == "missing" for row in compliance):
        actions.append({"priority": "critical", "title": "Close missing compliance evidence", "reason": "The compliance matrix contains missing evidence that can invalidate a bid decision.", "href": ""})
    if pricing["score"] < 75:
        actions.append({"priority": "high", "title": "Build pricing basis", "reason": pricing["warning"], "href": ""})
    if teaming:
        actions.append({"priority": "medium", "title": "Validate teaming shortlist", "reason": "Review partner capability, availability, OCI/conflict, and role before sending invitations.", "href": "/network"})

    return {
        "generated_at": timezone.now().isoformat(),
        "opportunity": {
            "source_id": opportunity.source_id,
            "title": opportunity.title,
            "agency": opportunity.agency,
            "naics": opportunity.naics_code,
            "psc": opportunity.psc_code,
            "source_url": opportunity.source_url,
        },
        "incumbent": incumbent,
        "competitors": competitors,
        "similar_contracts": similar,
        "teaming_recommendations": teaming,
        "compliance_matrix": compliance,
        "pricing_readiness": pricing,
        "win_strategy": {
            "strengths": strengths,
            "gaps": gaps,
            "discriminators": discriminators,
            "customer_evaluation_hypotheses": evaluation_hypotheses,
            "warning": "Win strategy is decision support. Official solicitation language, customer engagement, and validated company evidence take precedence.",
        },
        "recommended_actions": actions,
        "labels": {
            "official_historical_award": "Official historical award data",
            "derived_from_official_awards": "Inference derived from official award history",
            "inferred_competitor": "Likely competitor inference — not an official bidder list",
            "forgegov_network_match": "ForgeGov company-network match",
        },
    }
