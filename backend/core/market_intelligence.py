from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import ExtractYear
from django.utils import timezone

from .models import Award, Contact, NetworkConnection, Opportunity, OrganizationProfile, Vendor


LEGAL_SUFFIXES = {
    "CO", "COMPANY", "CORP", "CORPORATION", "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD",
}


def normalized_vendor_name(value: str) -> str:
    words = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper()).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _number(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _award_payload(row: Award) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "award_number": row.award_number,
        "parent_award_number": row.parent_award_number,
        "description": row.description,
        "recipient_name": row.recipient_name,
        "recipient_uei": row.recipient_uei,
        "recipient_cage": row.recipient_cage,
        "awarding_agency": row.awarding_agency,
        "awarding_office": row.awarding_office,
        "obligated_amount": _number(row.obligated_amount),
        "potential_amount": _number(row.potential_amount),
        "start_date": _iso(row.start_date),
        "end_date": _iso(row.end_date),
        "naics_code": row.naics_code,
        "psc_code": row.psc_code,
        "award_type": row.award_type,
        "source_url": row.source_url,
        "classification": "official_historical_award",
    }


def _vendor_awards(*, vendor: Vendor | None = None, name: str = "", uei: str = "", cage: str = ""):
    resolved_name = str(name or getattr(vendor, "name", "") or "").strip()
    resolved_uei = str(uei or getattr(vendor, "uei", "") or "").strip()
    resolved_cage = str(cage or getattr(vendor, "cage_code", "") or "").strip()
    identity = Q()
    if resolved_uei:
        identity |= Q(recipient_uei__iexact=resolved_uei)
    if resolved_cage:
        identity |= Q(recipient_cage__iexact=resolved_cage)
    if resolved_name:
        identity |= Q(recipient_name__iexact=resolved_name)
        normalized = normalized_vendor_name(resolved_name)
        first_word = normalized.split()[0] if normalized else ""
        if first_word:
            candidate_names = Award.objects.filter(recipient_name__icontains=first_word).exclude(recipient_name="").values_list("recipient_name", flat=True).distinct()[:500]
            aliases = [candidate for candidate in candidate_names if normalized_vendor_name(candidate) == normalized]
            if aliases:
                identity |= Q(recipient_name__in=aliases)
    return Award.objects.filter(jurisdiction_level="federal").filter(identity) if identity else Award.objects.none()


def vendor_dossier(*, organization, vendor_id: int | None = None, name: str = "", uei: str = "", cage: str = "") -> dict[str, Any]:
    vendor = None
    if vendor_id:
        vendor = Vendor.objects.filter(pk=vendor_id).first()
    if not vendor and uei:
        vendor = Vendor.objects.filter(uei__iexact=uei).order_by("id").first()
    if not vendor and cage:
        vendor = Vendor.objects.filter(cage_code__iexact=cage).order_by("id").first()
    if not vendor and name:
        vendor = Vendor.objects.filter(name__iexact=name).order_by("id").first()

    resolved_name = str(getattr(vendor, "name", "") or name).strip()
    awards = _vendor_awards(vendor=vendor, name=resolved_name, uei=uei, cage=cage)
    if not resolved_name:
        first = awards.order_by("-start_date", "-updated_at").first()
        resolved_name = first.recipient_name if first else ""

    totals = awards.aggregate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), potential=Sum("potential_amount"),
        latest_end=Max("end_date"), freshness=Max("source_updated_at"),
    )
    top_agencies = list(awards.exclude(awarding_agency="").values("awarding_agency").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated", "awarding_agency")[:10])
    top_offices = list(awards.exclude(awarding_office="").values("awarding_office").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated", "awarding_office")[:10])
    top_naics = list(awards.exclude(naics_code="").values("naics_code").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated", "naics_code")[:10])
    top_psc = list(awards.exclude(psc_code="").values("psc_code").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated", "psc_code")[:10])
    fiscal_years = list(awards.filter(start_date__isnull=False).annotate(year=ExtractYear("start_date")).values("year").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("year"))
    vehicles = awards.filter(award_type__in=[Award.AwardType.IDV, Award.AwardType.VEHICLE]).order_by("-end_date", "-potential_amount")[:10]
    contacts = list(Contact.objects.filter(organization=organization, vendor_name__iexact=resolved_name).values(
        "id", "full_name", "title", "email", "phone", "last_contacted_at",
    )[:20]) if resolved_name else []
    return {
        "identity": {
            "id": vendor.id if vendor else None,
            "name": resolved_name,
            "normalized_name": normalized_vendor_name(resolved_name),
            "uei": str(getattr(vendor, "uei", "") or uei),
            "cage_code": str(getattr(vendor, "cage_code", "") or cage),
            "city": str(getattr(vendor, "city", "")),
            "state": str(getattr(vendor, "state", "")),
            "website": str(getattr(vendor, "website", "")),
            "socioeconomic_statuses": list(getattr(vendor, "socioeconomic_statuses", []) or []),
        },
        "metrics": {
            "award_count": totals["award_count"] or 0,
            "obligated_amount": _number(totals["obligated"]),
            "potential_amount": _number(totals["potential"]),
            "agency_count": awards.exclude(awarding_agency="").values("awarding_agency").distinct().count(),
            "active_awards": awards.filter(end_date__gte=timezone.now().date()).count(),
            "latest_end": _iso(totals["latest_end"]),
        },
        "top_agencies": top_agencies,
        "top_offices": top_offices,
        "top_naics": top_naics,
        "top_psc": top_psc,
        "fiscal_years": fiscal_years,
        "vehicles": [_award_payload(row) for row in vehicles],
        "recent_awards": [_award_payload(row) for row in awards.order_by("-start_date", "-updated_at")[:15]],
        "contacts": contacts,
        "evidence": {
            "classification": "forgegov_rollup_of_official_awards",
            "latest_source_update": _iso(totals["freshness"]),
            "warning": "Historical federal award evidence does not confirm current bidder intent, capability, or future performance.",
        },
    }


def compare_vendors(*, organization, identities: list[str]) -> dict[str, Any]:
    cleaned = [item.strip() for item in identities if item.strip()][:4]
    dossiers = [vendor_dossier(organization=organization, name=item) for item in cleaned]
    return {
        "vendors": dossiers,
        "count": len(dossiers),
        "classification": "forgegov_comparison_of_official_award_history",
        "warning": "Comparison uses stored historical evidence and is not a source-selection prediction.",
    }


def agency_buying_patterns(*, name: str) -> dict[str, Any]:
    name = name.strip()
    awards = Award.objects.filter(jurisdiction_level="federal").filter(
        Q(awarding_agency__icontains=name) | Q(funding_agency__icontains=name)
    ) if name else Award.objects.none()
    opportunities = Opportunity.objects.filter(
        Q(agency__icontains=name) | Q(subagency__icontains=name) | Q(office__icontains=name)
    ) if name else Opportunity.objects.none()
    totals = awards.aggregate(award_count=Count("id"), obligated=Sum("obligated_amount"), freshness=Max("source_updated_at"))
    by_year = list(awards.filter(start_date__isnull=False).annotate(year=ExtractYear("start_date")).values("year").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), vendor_count=Count("recipient_name", distinct=True),
    ).order_by("year"))
    top_vendors = list(awards.exclude(recipient_name="").values("recipient_name", "recipient_uei").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), latest_end=Max("end_date"),
    ).order_by("-obligated", "recipient_name")[:15])
    top_offices = list(awards.exclude(awarding_office="").values("awarding_office").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated")[:10])
    top_categories = list(awards.exclude(naics_code="").values("naics_code").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), vendor_count=Count("recipient_name", distinct=True),
    ).order_by("-obligated")[:10])
    total_obligated = _number(totals["obligated"])
    leading = _number(top_vendors[0]["obligated"]) if top_vendors else 0
    return {
        "agency": name,
        "metrics": {
            "award_count": totals["award_count"] or 0,
            "obligated_amount": total_obligated,
            "vendor_count": awards.exclude(recipient_name="").values("recipient_name").distinct().count(),
            "active_opportunities": opportunities.filter(active=True).count(),
            "leading_vendor_share": round(leading / total_obligated * 100, 1) if total_obligated else 0,
        },
        "fiscal_years": by_year,
        "top_vendors": top_vendors,
        "top_offices": top_offices,
        "top_categories": top_categories,
        "recent_opportunities": list(opportunities.filter(active=True).order_by("-posted_date").values(
            "source_id", "title", "agency", "office", "naics_code", "psc_code", "posted_date", "response_deadline",
        )[:10]),
        "evidence": {
            "classification": "forgegov_rollup_of_official_awards_and_opportunities",
            "latest_source_update": _iso(totals["freshness"]),
            "warning": "Buying patterns describe stored history and do not prove future acquisition intent.",
        },
    }


def market_map(*, category_type: str, code: str = "") -> dict[str, Any]:
    category_type = category_type if category_type in {"naics", "psc"} else "naics"
    field = "naics_code" if category_type == "naics" else "psc_code"
    awards = Award.objects.filter(jurisdiction_level="federal").exclude(**{field: ""})
    if code:
        awards = awards.filter(**{field: code})
    categories = list(awards.values(field).annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), vendor_count=Count("recipient_name", distinct=True), agency_count=Count("awarding_agency", distinct=True),
    ).order_by("-obligated")[:25])
    vendors = list(awards.exclude(recipient_name="").values("recipient_name").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), agency_count=Count("awarding_agency", distinct=True),
    ).order_by("-obligated")[:20])
    agencies = list(awards.exclude(awarding_agency="").values("awarding_agency").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"), vendor_count=Count("recipient_name", distinct=True),
    ).order_by("-obligated")[:20])
    edges = list(awards.exclude(recipient_name="").exclude(awarding_agency="").values("awarding_agency", "recipient_name").annotate(
        award_count=Count("id"), obligated=Sum("obligated_amount"),
    ).order_by("-obligated")[:50])
    return {
        "category_type": category_type,
        "code": code,
        "categories": [{"code": row.pop(field), **row} for row in categories],
        "vendors": vendors,
        "agencies": agencies,
        "relationships": edges,
        "classification": "forgegov_market_map_from_official_award_history",
        "warning": "Market concentration reflects stored award coverage, not the entire addressable market.",
    }


def vehicle_analysis(*, query: str = "") -> dict[str, Any]:
    awards = Award.objects.filter(jurisdiction_level="federal", award_type__in=[Award.AwardType.IDV, Award.AwardType.VEHICLE])
    if query:
        awards = awards.filter(Q(award_number__icontains=query) | Q(description__icontains=query) | Q(recipient_name__icontains=query) | Q(awarding_agency__icontains=query))
    totals = awards.aggregate(count=Count("id"), obligated=Sum("obligated_amount"), potential=Sum("potential_amount"), freshness=Max("source_updated_at"))
    holders = list(awards.exclude(recipient_name="").values("recipient_name", "recipient_uei").annotate(
        vehicle_count=Count("id"), obligated=Sum("obligated_amount"), potential=Sum("potential_amount"), latest_end=Max("end_date"),
    ).order_by("-potential")[:20])
    agencies = list(awards.exclude(awarding_agency="").values("awarding_agency").annotate(
        vehicle_count=Count("id"), obligated=Sum("obligated_amount"), potential=Sum("potential_amount"),
    ).order_by("-potential")[:15])
    return {
        "metrics": {"vehicle_count": totals["count"] or 0, "obligated_amount": _number(totals["obligated"]), "potential_amount": _number(totals["potential"])},
        "holders": holders,
        "agencies": agencies,
        "expiring": [_award_payload(row) for row in awards.filter(end_date__gte=timezone.now().date()).order_by("end_date")[:20]],
        "recent": [_award_payload(row) for row in awards.order_by("-start_date", "-updated_at")[:20]],
        "evidence": {"classification": "official_stored_vehicle_awards", "latest_source_update": _iso(totals["freshness"]), "warning": "Potential value is a ceiling or potential amount, not guaranteed spending."},
    }


def teaming_recommendations(*, organization, naics: str = "", psc: str = "", state: str = "", required_vehicle: str = "") -> dict[str, Any]:
    own = OrganizationProfile.objects.filter(organization=organization).first()
    existing = NetworkConnection.objects.filter(Q(requester=organization) | Q(recipient=organization))
    relationship: dict[int, str] = {}
    for row in existing:
        other_id = row.recipient_id if row.requester_id == organization.id else row.requester_id
        relationship[other_id] = row.status
    results = []
    profiles = OrganizationProfile.objects.filter(is_public=True, accepting_partners=True).exclude(organization=organization).select_related("organization")[:500]
    for profile in profiles:
        if relationship.get(profile.organization_id) == NetworkConnection.Status.BLOCKED:
            continue
        score = 20
        reasons = []
        gaps = []
        profile_naics = {str(item) for item in profile.naics_codes or []}
        profile_psc = {str(item) for item in profile.psc_codes or []}
        vehicles = {str(item).lower() for item in profile.contract_vehicles or []}
        if naics:
            if naics in profile_naics:
                score += 30
                reasons.append(f"NAICS {naics} match")
            else:
                gaps.append(f"NAICS {naics} not published")
        if psc:
            if psc in profile_psc:
                score += 20
                reasons.append(f"PSC {psc} match")
            else:
                gaps.append(f"PSC {psc} not published")
        if state and profile.state.upper() == state.upper():
            score += 10
            reasons.append(f"Located in {state.upper()}")
        if required_vehicle:
            if required_vehicle.lower() in vehicles:
                score += 20
                reasons.append(f"Published vehicle: {required_vehicle}")
            else:
                gaps.append(f"Vehicle {required_vehicle} not published")
        if profile.verified:
            score += 10
            reasons.append("Verified ForgeGov profile")
        if own:
            complementary = sorted(set(profile.capabilities or []) - set(own.capabilities or []))[:3]
            if complementary:
                score += min(10, len(complementary) * 3)
                reasons.append("Adds published capabilities: " + ", ".join(map(str, complementary)))
        if score <= 20:
            continue
        results.append({
            "organization_id": profile.organization_id,
            "name": profile.organization.name,
            "score": min(score, 100),
            "reasons": reasons,
            "gaps": gaps,
            "relationship_status": relationship.get(profile.organization_id, "none"),
            "verified": profile.verified,
            "state": profile.state,
            "href": f"/network?company={profile.organization_id}",
            "classification": "forgegov_network_profile_match",
        })
    results.sort(key=lambda row: (row["score"], row["verified"], row["name"]), reverse=True)
    return {
        "results": results[:50],
        "total_records": len(results[:50]),
        "warning": "Recommendations use published ForgeGov profiles. Validate capability, availability, eligibility, and vehicle access directly before relying on a partner.",
    }
