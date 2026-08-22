from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from .ai import ask_ai
from .document_intelligence import capture_readiness_summary
from .models import Award, OpportunityAnalysis, OpportunityDocument, OrganizationProfile, PipelineItem, Task


def _bounded(value: float | int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(float(value))))


def _severity(score: int) -> str:
    if score >= 75:
        return "low"
    if score >= 50:
        return "medium"
    return "high"


def _latest_pipeline_item(organization, opportunity):
    return PipelineItem.objects.filter(organization=organization, opportunity=opportunity).select_related("project_room").order_by("-updated_at").first()


def _org_profile(organization):
    return OrganizationProfile.objects.filter(organization=organization).first()


def _document_signals(documents) -> dict[str, Any]:
    readiness = capture_readiness_summary(documents)
    structured = [((doc.metadata or {}).get("structured_intelligence") or {}) for doc in documents if doc.status == OpportunityDocument.Status.READY]
    unique = lambda key: sorted({str(item).strip() for row in structured for item in (row.get(key) or []) if str(item).strip()})
    return {
        "readiness": readiness,
        "section_l": any(row.get("section_l_detected") for row in structured),
        "section_m": any(row.get("section_m_detected") for row in structured),
        "clins": unique("clins"),
        "clauses": unique("clauses"),
        "key_dates": unique("key_dates"),
        "certifications": unique("certifications"),
        "cmmc": unique("cmmc"),
        "deliverables": unique("deliverables"),
        "labor_categories": unique("labor_categories"),
    }


def _capability_score(organization, opportunity) -> tuple[int, list[str]]:
    profile = _org_profile(organization)
    reasons: list[str] = []
    if not profile:
        return 45, ["Complete the company profile to improve capability-fit scoring."]
    score = 45
    naics = {str(code).strip() for code in (profile.naics_codes or [])}
    pscs = {str(code).strip() for code in (profile.psc_codes or [])}
    if opportunity.naics_code and opportunity.naics_code in naics:
        score += 30
        reasons.append(f"Company profile includes NAICS {opportunity.naics_code}.")
    elif opportunity.naics_code:
        reasons.append(f"NAICS {opportunity.naics_code} is not yet listed on the company profile.")
    if opportunity.psc_code and opportunity.psc_code in pscs:
        score += 15
        reasons.append(f"Company profile includes PSC {opportunity.psc_code}.")
    title_words = {word.lower() for word in opportunity.title.split() if len(word) >= 5}
    capability_text = " ".join([*(profile.capabilities or []), profile.description or "", profile.tagline or ""]).lower()
    overlap = sorted(word for word in title_words if word in capability_text)
    if overlap:
        score += min(10, len(overlap) * 2)
        reasons.append(f"Capability profile overlaps opportunity terms: {', '.join(overlap[:5])}.")
    if not reasons:
        reasons.append("Capability fit is based on limited profile evidence.")
    return _bounded(score), reasons


def _competition_score(opportunity) -> tuple[int, dict[str, Any]]:
    awards = Award.objects.all()
    filters = Q()
    if opportunity.agency:
        filters |= Q(awarding_agency__icontains=opportunity.agency) | Q(funding_agency__icontains=opportunity.agency)
    if opportunity.naics_code:
        filters |= Q(naics_code=opportunity.naics_code)
    if opportunity.psc_code:
        filters |= Q(psc_code=opportunity.psc_code)
    if filters:
        awards = awards.filter(filters)
    sample = list(awards.exclude(recipient_name="").order_by("-start_date", "-updated_at")[:250])
    recipients: dict[str, int] = {}
    for award in sample:
        name = (award.recipient_name or "").strip()
        if name:
            recipients[name] = recipients.get(name, 0) + 1
    ranked = sorted(recipients.items(), key=lambda row: row[1], reverse=True)
    competitor_count = len(ranked)
    score = 88 if competitor_count <= 3 else 76 if competitor_count <= 8 else 62 if competitor_count <= 15 else 48
    return score, {
        "historical_vendor_count": competitor_count,
        "top_historical_vendors": [{"name": name, "matching_awards": count} for name, count in ranked[:5]],
        "classification": "historical_market_signal",
        "warning": "Competition score uses historical award overlap and is not an official bidder list.",
    }


def _schedule_score(opportunity) -> tuple[int, dict[str, Any]]:
    if not opportunity.response_deadline:
        return 45, {"days_remaining": None, "detail": "Response deadline is missing from the stored opportunity."}
    delta = opportunity.response_deadline - timezone.now()
    days = delta.total_seconds() / 86400
    if days < 0:
        score = 10
    elif days < 3:
        score = 25
    elif days < 7:
        score = 45
    elif days < 14:
        score = 65
    elif days < 30:
        score = 82
    else:
        score = 94
    return score, {"days_remaining": round(days, 1), "detail": f"Approximately {max(0, round(days, 1))} days remain before the response deadline."}


def _pricing_score(pipeline) -> tuple[int, str]:
    if not pipeline:
        return 35, "Add the opportunity to the pipeline to establish value and pricing assumptions."
    if pipeline.estimated_value:
        return 82, "Estimated opportunity value is recorded in the capture pipeline."
    if pipeline.stage in {PipelineItem.Stage.PROPOSAL, PipelineItem.Stage.SUBMITTED}:
        return 62, "Pursuit is in proposal development but estimated value is still missing."
    return 45, "Pricing assumptions have not been established yet."


def _past_performance_score(organization, opportunity) -> tuple[int, str]:
    org_name = (organization.name or "").strip()
    if not org_name:
        return 40, "Workspace organization name is unavailable for historical award matching."
    awards = Award.objects.filter(recipient_name__icontains=org_name)
    relevance = Q()
    if opportunity.naics_code:
        relevance |= Q(naics_code=opportunity.naics_code)
    if opportunity.psc_code:
        relevance |= Q(psc_code=opportunity.psc_code)
    if relevance:
        awards = awards.filter(relevance)
    count = awards.count()
    if count >= 5:
        return 92, f"ForgeGov found {count} potentially relevant historical awards for the workspace organization."
    if count:
        return 70, f"ForgeGov found {count} potentially relevant historical award(s) for the workspace organization."
    return 38, "No matching stored USAspending award history was found for the workspace organization."


def _risk_row(key: str, label: str, score: int, reason: str, mitigation: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "score": score,
        "severity": _severity(score),
        "reason": reason,
        "mitigation": mitigation,
    }


def build_capture_assessment(*, organization, opportunity, include_ai: bool = False, refresh_ai: bool = False, user=None) -> dict[str, Any]:
    documents = list(OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).prefetch_related("chunks"))
    doc = _document_signals(documents)
    pipeline = _latest_pipeline_item(organization, opportunity)
    capability_score, capability_reasons = _capability_score(organization, opportunity)
    competition_score, competition = _competition_score(opportunity)
    schedule_score, schedule = _schedule_score(opportunity)
    pricing_score, pricing_detail = _pricing_score(pipeline)
    past_score, past_detail = _past_performance_score(organization, opportunity)
    compliance_score = _bounded((100 if doc["section_l"] else 35) * 0.22 + (100 if doc["section_m"] else 35) * 0.22 + (90 if (doc["clauses"] or doc["certifications"] or doc["cmmc"]) else 45) * 0.28 + doc["readiness"]["score"] * 0.28)
    document_score = doc["readiness"]["score"]
    health_score = _bounded(
        capability_score * 0.22
        + document_score * 0.18
        + compliance_score * 0.18
        + schedule_score * 0.14
        + pricing_score * 0.12
        + competition_score * 0.08
        + past_score * 0.08
    )
    pipeline_probability = int(pipeline.probability_of_win or 0) if pipeline else 0
    win_probability = _bounded((health_score * 0.75 + pipeline_probability * 0.25) if pipeline_probability else max(10, health_score - 8), 5, 95)

    evidence_checks = [
        bool(documents), doc["section_l"], doc["section_m"], bool(doc["clins"]), bool(opportunity.response_deadline),
        bool(opportunity.naics_code), bool(opportunity.psc_code), bool(pipeline), bool(pipeline and pipeline.estimated_value), past_score >= 70,
    ]
    evidence_coverage = _bounded(sum(1 for row in evidence_checks if row) / len(evidence_checks) * 100)
    recommendation = "bid" if health_score >= 72 else "hold" if health_score >= 52 else "no_bid"
    confidence = _bounded(55 + evidence_coverage * 0.4, 55, 95)

    readiness = [
        {"key": "documents", "label": "Government documents indexed", "status": "complete" if documents and document_score >= 40 else "missing", "detail": f"{doc['readiness']['ready_documents']} document(s) indexed."},
        {"key": "section_l", "label": "Section L / submission instructions", "status": "complete" if doc["section_l"] else "missing", "detail": "Detected in indexed document evidence." if doc["section_l"] else "Section L indicators have not been detected."},
        {"key": "section_m", "label": "Section M / evaluation criteria", "status": "complete" if doc["section_m"] else "missing", "detail": "Detected in indexed document evidence." if doc["section_m"] else "Section M indicators have not been detected."},
        {"key": "clins", "label": "CLIN / line-item structure", "status": "complete" if doc["clins"] else "needs_review", "detail": f"{len(doc['clins'])} line-item identifiers detected." if doc["clins"] else "No CLIN/SUBCLIN/ELIN identifiers detected yet."},
        {"key": "security", "label": "Security and compliance evidence", "status": "complete" if (doc["clauses"] or doc["certifications"] or doc["cmmc"]) else "needs_review", "detail": f"{len(doc['clauses'])} clause and {len(doc['certifications']) + len(doc['cmmc'])} certification/security signal(s)."},
        {"key": "past_performance", "label": "Past performance evidence", "status": "complete" if past_score >= 70 else "missing", "detail": past_detail},
        {"key": "pricing", "label": "Pricing / value assumptions", "status": "complete" if pricing_score >= 70 else "needs_review", "detail": pricing_detail},
        {"key": "deadline", "label": "Response deadline", "status": "complete" if opportunity.response_deadline else "missing", "detail": schedule["detail"]},
    ]
    readiness_score = _bounded(sum(100 if item["status"] == "complete" else 55 if item["status"] == "needs_review" else 0 for item in readiness) / len(readiness))

    risks = [
        _risk_row("technical", "Technical", capability_score, "; ".join(capability_reasons[:2]), "Validate technical approach and capability gaps with the capture team."),
        _risk_row("schedule", "Schedule", schedule_score, schedule["detail"], "Build the proposal calendar and assign owners to every near-term milestone."),
        _risk_row("compliance", "Compliance", compliance_score, "Structured document evidence is incomplete." if compliance_score < 70 else "Key compliance evidence is present in indexed documents.", "Close every missing Section L/M and clause requirement before final bid approval."),
        _risk_row("pricing", "Pricing", pricing_score, pricing_detail, "Establish pricing assumptions, subcontractor inputs, and review dates."),
        _risk_row("competition", "Competition", competition_score, competition["warning"], "Research incumbent and top historical awardees; validate likely competitors with customer intelligence."),
        _risk_row("customer", "Customer", 72 if opportunity.agency else 42, f"Customer organization: {opportunity.agency or 'not identified'}.", "Capture customer mission, buying office, stakeholders, and recent buying behavior."),
    ]

    actions: list[dict[str, Any]] = []
    def action(priority: str, title: str, reason: str, href: str = ""):
        actions.append({"priority": priority, "title": title, "reason": reason, "href": href})
    if not documents or document_score < 40:
        action("critical", "Index solicitation documents", "Capture scoring is limited until the government attachments are indexed.")
    if not doc["section_l"] or not doc["section_m"]:
        action("high", "Locate Sections L and M", "Submission instructions or evaluation criteria are missing from extracted evidence.")
    if past_score < 70:
        action("high", "Validate relevant past performance", past_detail)
    if pricing_score < 70:
        action("high", "Establish pricing assumptions", pricing_detail)
    if competition["historical_vendor_count"]:
        action("medium", "Research historical competitors", f"ForgeGov found {competition['historical_vendor_count']} historical vendor signals.", "/intelligence/awards")
    if not pipeline:
        action("medium", "Add opportunity to pipeline", "Persist ownership, value, probability, and next actions in the capture pipeline.", "/capture/pipelines")
    if opportunity.response_deadline and schedule.get("days_remaining") is not None and schedule["days_remaining"] < 14:
        action("critical", "Lock the proposal schedule", schedule["detail"])
    if not actions:
        action("medium", "Validate capture assumptions", "The evidence base is strong enough to move into deeper win-strategy analysis.")

    timeline = []
    for label, when, source in [
        ("Posted", opportunity.posted_date, "SAM.gov"),
        ("Source modified", opportunity.source_modified_at, "SAM.gov"),
        ("Response deadline", opportunity.response_deadline, "SAM.gov"),
        ("Archive date", opportunity.archive_date, "SAM.gov"),
    ]:
        if when:
            timeline.append({"label": label, "date": when.isoformat(), "source": source, "kind": "official"})
    for date_text in doc["key_dates"][:8]:
        timeline.append({"label": "Document date candidate", "date": date_text, "source": "Indexed solicitation", "kind": "document_signal"})

    deterministic_summary = (
        f"{opportunity.agency or 'The customer'} is pursuing {opportunity.title}. "
        f"ForgeGov currently scores this pursuit at {health_score}/100 for overall capture health and {readiness_score}/100 for proposal readiness. "
        f"The strongest evidence is {'document coverage and compliance signals' if document_score >= 70 else 'the opportunity record itself'}, while the most important gaps are "
        f"{', '.join(item['label'] for item in readiness if item['status'] != 'complete') or 'limited'}."
    )

    fingerprint_source = "|".join([
        str(opportunity.updated_at.timestamp()),
        str(pipeline.updated_at.timestamp()) if pipeline else "no-pipeline",
        *sorted(doc.checksum for doc in documents if doc.checksum),
    ])
    fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()
    cached_ai = OpportunityAnalysis.objects.filter(
        organization=organization,
        opportunity=opportunity,
        project_room=None,
        analysis_type="capture_assessment",
        input_fingerprint=fingerprint,
    ).first()

    if include_ai and (refresh_ai or not cached_ai):
        source_context = [
            f"Opportunity: {opportunity.title}",
            f"Agency: {opportunity.agency}",
            f"NAICS: {opportunity.naics_code}",
            f"PSC: {opportunity.psc_code}",
            f"Set-aside: {opportunity.set_aside}",
            f"Response deadline: {opportunity.response_deadline}",
            f"Document readiness: {document_score}/100",
            f"Proposal readiness: {readiness_score}/100",
            f"Capability fit: {capability_score}/100",
            f"Competition posture: {competition_score}/100",
            f"Pricing readiness: {pricing_score}/100",
            f"Past performance evidence: {past_score}/100",
            f"Deterministic recommendation: {recommendation.upper()} with {confidence}% confidence",
            f"Missing readiness items: {', '.join(item['label'] for item in readiness if item['status'] != 'complete') or 'none'}",
        ]
        prompt = (
            "Create a concise executive capture brief using only the supplied ForgeGov evidence. "
            "Separate verified facts from analysis. Explain customer need, pursuit posture, major risks, proposal-readiness gaps, and the next three actions. "
            "Do not claim an incumbent, competitor, requirement, or win probability as fact unless the evidence explicitly supports it.\n\n"
            + "\n".join(source_context)
        )
        try:
            ai_result = ask_ai(message=prompt, history=[], organization=organization, user=user)
            cached_ai, _ = OpportunityAnalysis.objects.update_or_create(
                organization=organization,
                opportunity=opportunity,
                project_room=None,
                analysis_type="capture_assessment",
                input_fingerprint=fingerprint,
                defaults={
                    "content": ai_result.get("answer", ""),
                    "sources": [{"label": "[CAPTURE]", "type": "platform", "title": "ForgeGov capture evidence"}],
                    "model": ai_result.get("model", ""),
                    "created_by": user,
                },
            )
        except Exception:
            cached_ai = None

    return {
        "generated_at": timezone.now().isoformat(),
        "opportunity": {
            "source_id": opportunity.source_id,
            "title": opportunity.title,
            "agency": opportunity.agency,
            "solicitation_number": opportunity.solicitation_number,
            "naics": opportunity.naics_code,
            "psc": opportunity.psc_code,
            "response_deadline": opportunity.response_deadline,
        },
        "scores": {
            "health": health_score,
            "win_probability": win_probability,
            "proposal_readiness": readiness_score,
            "capability": capability_score,
            "documents": document_score,
            "compliance": compliance_score,
            "schedule": schedule_score,
            "pricing": pricing_score,
            "competition": competition_score,
            "past_performance": past_score,
        },
        "bid_decision": {
            "recommendation": recommendation,
            "confidence": confidence,
            "evidence_coverage": evidence_coverage,
            "rationale": capability_reasons + [pricing_detail, past_detail],
            "warning": "This is capture decision support, not a guaranteed win prediction or legal determination.",
        },
        "executive_summary": cached_ai.content if cached_ai and cached_ai.content else deterministic_summary,
        "ai_generated": bool(cached_ai and cached_ai.content),
        "readiness": readiness,
        "risks": risks,
        "actions": actions,
        "timeline": sorted(timeline, key=lambda row: str(row["date"])),
        "competition": competition,
        "document_signals": {
            "section_l": doc["section_l"],
            "section_m": doc["section_m"],
            "clins": len(doc["clins"]),
            "clauses": len(doc["clauses"]),
            "key_dates": len(doc["key_dates"]),
            "certifications": len(doc["certifications"]) + len(doc["cmmc"]),
            "deliverables": len(doc["deliverables"]),
        },
        "pipeline": {
            "id": pipeline.id if pipeline else None,
            "stage": pipeline.stage if pipeline else "not_added",
            "estimated_value": pipeline.estimated_value if pipeline else None,
            "probability_of_win": pipeline.probability_of_win if pipeline else 0,
            "next_action": pipeline.next_action if pipeline else "",
            "project_room_id": pipeline.project_room_id if pipeline else None,
        },
    }
