from __future__ import annotations

import re
from typing import Any

from django.db.models import Count, Sum

from .models import Award, Opportunity, PipelineItem, Vendor
from .serializers import AwardSerializer

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")
CONTRACT_RE = re.compile(r"\b(?:[A-Z0-9]{4,8}-\d{2}-[A-Z]-\d{3,6}|[A-Z0-9]{6,18})\b", re.I)


def _contact(raw: dict[str, Any]) -> dict[str, str]:
    value = str(raw.get("point_of_contact") or raw.get("contact") or "").strip()
    email = str(raw.get("contact_email") or "").strip()
    phone = str(raw.get("contact_phone") or "").strip()
    if not email:
        match = EMAIL_RE.search(value)
        email = match.group(0) if match else ""
    if not phone:
        match = PHONE_RE.search(value)
        phone = match.group(0) if match else ""
    name = value
    if email:
        name = name.replace(email, " ")
    if phone:
        name = name.replace(phone, " ")
    name = " ".join(name.replace("|", " ").replace(";", " ").split())
    return {"name": name[:255], "email": email[:254], "phone": phone[:80], "raw": value[:1000]}


def _prime_profile(prime_name: str) -> dict[str, Any]:
    if not prime_name:
        return {"name": "", "vendor": None, "award_summary": {}, "recent_awards": []}
    vendor = Vendor.objects.filter(name__iexact=prime_name).first() or Vendor.objects.filter(name__icontains=prime_name).order_by("name").first()
    awards = Award.objects.filter(recipient_name__iexact=prime_name)
    if not awards.exists():
        awards = Award.objects.filter(recipient_name__icontains=prime_name)
    totals = awards.aggregate(obligated=Sum("obligated_amount"), potential=Sum("potential_amount"), awards=Count("id"))
    agencies = list(
        awards.exclude(awarding_agency="")
        .values("awarding_agency")
        .annotate(awards=Count("id"), obligated=Sum("obligated_amount"))
        .order_by("-obligated")[:5]
    )
    return {
        "name": prime_name,
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "uei": vendor.uei,
            "cage_code": vendor.cage_code,
            "website": vendor.website,
            "city": vendor.city,
            "state": vendor.state,
            "naics_codes": vendor.naics_codes,
            "socioeconomic_statuses": vendor.socioeconomic_statuses,
        } if vendor else None,
        "award_summary": {
            "award_count": totals.get("awards") or 0,
            "obligated_amount": totals.get("obligated") or 0,
            "potential_amount": totals.get("potential") or 0,
            "top_agencies": agencies,
            "classification": "official_historical_award_intelligence",
        },
        "recent_awards": AwardSerializer(awards.order_by("-start_date", "-updated_at")[:10], many=True).data,
    }


def _parent_contract_candidates(opportunity: Opportunity, prime_name: str) -> list[dict[str, Any]]:
    raw = dict(opportunity.raw_data or {})
    explicit = []
    for key in ("parent_contract", "contract_number", "award_number", "referenced_idv", "referenced_idv_agency_identifier"):
        value = str(raw.get(key) or "").strip()
        if value and value not in explicit:
            explicit.append(value)
    text = f"{opportunity.title}\n{opportunity.description}\n{raw}"
    for candidate in CONTRACT_RE.findall(text):
        if any(char.isdigit() for char in candidate) and candidate not in explicit:
            explicit.append(candidate)
        if len(explicit) >= 12:
            break

    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for ref in explicit:
        for award in Award.objects.filter(award_number__icontains=ref).order_by("-obligated_amount")[:3]:
            if award.id in seen:
                continue
            seen.add(award.id)
            row = AwardSerializer(award).data
            row["match_reason"] = f"Reference {ref} appears in the SUBNet listing or source metadata."
            row["classification"] = "possible_parent_contract_reference"
            results.append(row)
    if not results and prime_name:
        related = Award.objects.filter(recipient_name__icontains=prime_name)
        if opportunity.naics_code:
            related = related.filter(naics_code=opportunity.naics_code)
        for award in related.order_by("-start_date", "-obligated_amount")[:5]:
            row = AwardSerializer(award).data
            row["match_reason"] = "Historical prime award with matching prime contractor and NAICS; verify before treating as the parent contract."
            row["classification"] = "historical_prime_award_candidate"
            results.append(row)
    return results[:8]


def build_subcontract_workspace(*, opportunity: Opportunity, organization) -> dict[str, Any]:
    raw = dict(opportunity.raw_data or {})
    prime_name = str(raw.get("prime_contractor") or opportunity.agency or "").strip()
    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).select_related("owner").order_by("-updated_at").first()
    return {
        "opportunity": {
            "source_id": opportunity.source_id,
            "source": opportunity.source,
            "title": opportunity.title,
            "description": opportunity.description,
            "prime_contractor": prime_name,
            "solicitation_number": opportunity.solicitation_number,
            "naics": opportunity.naics_code,
            "psc": opportunity.psc_code,
            "closing_date": opportunity.response_deadline,
            "performance_start": raw.get("performance_start") or raw.get("performance_start_date") or "",
            "place_of_performance": opportunity.place_of_performance,
            "source_url": opportunity.source_url,
            "active": opportunity.active,
            "notice_type": opportunity.notice_type_raw or "Subcontracting Opportunity",
            "source_metadata": {
                "source_name": raw.get("source_name") or "SBA SUBNet",
                "observed_at": raw.get("observed_at") or opportunity.updated_at,
                "classification": "official_subcontract_listing",
            },
        },
        "contact": _contact(raw),
        "prime": _prime_profile(prime_name),
        "parent_contract_candidates": _parent_contract_candidates(opportunity, prime_name),
        "pipeline": {
            "active": bool(pipeline),
            "id": pipeline.id if pipeline else None,
            "stage": pipeline.stage if pipeline else "",
            "owner": (pipeline.owner.get_full_name() or pipeline.owner.email) if pipeline and pipeline.owner else "",
            "next_action": pipeline.next_action if pipeline else "",
            "probability_of_win": pipeline.probability_of_win if pipeline else 0,
        },
        "capture_links": {
            "company_profile": f"/participants/vendors/profile?name={prime_name}" if prime_name else "",
            "pipeline": f"/capture/pipelines/{pipeline.id}/open" if pipeline else "/capture/pipelines",
            "project_rooms": "/project-rooms",
        },
        "warnings": [
            "Parent contract candidates are historical/reference matches until verified against the prime contractor or official source.",
            "Historical federal awards describe past government performance and do not prove that a company is pursuing this subcontract opportunity.",
        ],
    }
