from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import Opportunity


class IntegrationError(RuntimeError):
    pass


NOTICE_TYPE_MAP = {
    "o": Opportunity.NoticeType.SOLICITATION,
    "solicitation": Opportunity.NoticeType.SOLICITATION,
    "k": Opportunity.NoticeType.COMBINED,
    "combined synopsis/solicitation": Opportunity.NoticeType.COMBINED,
    "r": Opportunity.NoticeType.SOURCES_SOUGHT,
    "sources sought": Opportunity.NoticeType.SOURCES_SOUGHT,
    "p": Opportunity.NoticeType.PRESOLICITATION,
    "presolicitation": Opportunity.NoticeType.PRESOLICITATION,
    "pre solicitation": Opportunity.NoticeType.PRESOLICITATION,
    "a": Opportunity.NoticeType.AWARD,
    "award notice": Opportunity.NoticeType.AWARD,
    "s": Opportunity.NoticeType.SPECIAL,
    "special notice": Opportunity.NoticeType.SPECIAL,
    "u": Opportunity.NoticeType.JUSTIFICATION,
    "justification": Opportunity.NoticeType.JUSTIFICATION,
    "g": Opportunity.NoticeType.SURPLUS,
    "sale of surplus property": Opportunity.NoticeType.SURPLUS,
}


def _sam_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None

    normalized = value.strip().replace("Z", "+00:00")
    parsed = parse_datetime(normalized)
    if parsed is None:
        parsed_date = parse_date(normalized[:10])
        if parsed_date:
            parsed = datetime.combine(parsed_date, datetime.min.time())

    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed




def _sam_date_param(value: str | None, fallback: date) -> str:
    if not value:
        return fallback.strftime("%m/%d/%Y")
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise IntegrationError("SAM.gov dates must use YYYY-MM-DD or MM/DD/YYYY format.")

def _safe_text(value: Any, *, max_length: int | None = None) -> str:
    text = "" if value is None else str(value).strip()
    return text[:max_length] if max_length else text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _organization_parts(record: dict[str, Any]) -> tuple[str, str, str, str]:
    path = _safe_text(record.get("fullParentPathName"))
    segments = [segment.strip() for segment in path.split(".") if segment.strip()]
    agency = segments[0] if segments else _safe_text(record.get("department"), max_length=255)
    subagency = segments[1] if len(segments) > 1 else _safe_text(record.get("subtier"), max_length=255)
    office = segments[-1] if len(segments) > 2 else _safe_text(record.get("office"), max_length=255)
    return agency[:255], subagency[:255], office[:255], path


def _place_of_performance(record: dict[str, Any]) -> str:
    data = record.get("placeOfPerformance") or {}
    if not isinstance(data, dict):
        return _safe_text(data, max_length=500)

    parts: list[str] = []
    city = data.get("city")
    state = data.get("state")
    country = data.get("country")
    zip_code = data.get("zip")

    for value in (city.get("name") if isinstance(city, dict) else city,
                  state.get("name") if isinstance(state, dict) else state,
                  zip_code,
                  country.get("name") if isinstance(country, dict) else country):
        if value:
            parts.append(str(value).strip())
    return ", ".join(dict.fromkeys(parts))[:500]


def _notice_type(raw_value: Any) -> str:
    key = _safe_text(raw_value).lower()
    return NOTICE_TYPE_MAP.get(key, Opportunity.NoticeType.OTHER)


def upsert_sam_opportunity(record: dict[str, Any]) -> tuple[Opportunity, bool]:
    notice_id = _safe_text(record.get("noticeId") or record.get("noticeid"), max_length=255)
    if not notice_id:
        raise IntegrationError("SAM.gov returned an opportunity without a notice ID.")

    agency, subagency, office, organization_path = _organization_parts(record)
    raw_type = record.get("type") or record.get("baseType")
    # The API-provided uiLink can require a SAM.gov role and return a 404 for public users.
    source_url = f"https://sam.gov/opp/{notice_id}/view"
    resource_links = record.get("resourceLinks") if isinstance(record.get("resourceLinks"), list) else []

    defaults = {
        "source": "sam.gov",
        "solicitation_number": _safe_text(record.get("solicitationNumber"), max_length=120),
        "title": _safe_text(record.get("title"), max_length=500) or "Untitled SAM.gov opportunity",
        "description": "",
        "agency": agency,
        "subagency": subagency,
        "office": office,
        "organization_path": organization_path,
        "notice_type": _notice_type(raw_type),
        "notice_type_raw": _safe_text(raw_type, max_length=120),
        "naics_code": _safe_text(record.get("naicsCode"), max_length=12),
        "psc_code": _safe_text(record.get("classificationCode"), max_length=12),
        "set_aside": _safe_text(record.get("typeOfSetAsideDescription") or record.get("setAside"), max_length=255),
        "set_aside_code": _safe_text(record.get("typeOfSetAside") or record.get("setAsideCode"), max_length=50),
        "posted_date": _sam_datetime(record.get("postedDate")),
        "response_deadline": _sam_datetime(record.get("responseDeadLine") or record.get("responseDeadline")),
        "archive_date": _sam_datetime(record.get("archiveDate")),
        "place_of_performance": _place_of_performance(record),
        "active": _safe_text(record.get("active")).lower() not in {"no", "false", "0"},
        "source_url": source_url,
        "resource_links": resource_links,
        "raw_data": record,
    }
    return Opportunity.objects.update_or_create(source_id=notice_id, defaults=defaults)


def _build_sam_params(
    *,
    keyword: str = "",
    limit: int = 25,
    offset: int = 0,
    posted_from: str | None = None,
    posted_to: str | None = None,
    procurement_type: str = "",
    solicitation_number: str = "",
    notice_id: str = "",
    agency: str = "",
    naics: str = "",
    psc: str = "",
    state: str = "",
    set_aside: str = "",
    response_from: str = "",
    response_to: str = "",
    opportunity_status: str = "",
) -> dict[str, Any]:
    today = date.today()
    params: dict[str, Any] = {
        "api_key": settings.SAM_GOV_API_KEY,
        "limit": max(1, min(limit, 1000)),
        "offset": max(0, offset),
        "postedFrom": _sam_date_param(posted_from, today - timedelta(days=30)),
        "postedTo": _sam_date_param(posted_to, today),
    }

    optional = {
        "title": keyword,
        "ptype": procurement_type,
        "solnum": solicitation_number,
        "noticeid": notice_id,
        "organizationName": agency,
        "ncode": naics,
        "ccode": psc,
        "state": state,
        "typeOfSetAside": set_aside,
        "rdlfrom": response_from,
        "rdlto": response_to,
        "status": opportunity_status,
    }
    params.update({key: value for key, value in optional.items() if value})
    return params


def search_sam_opportunities(*, persist: bool = False, **filters: Any) -> dict[str, Any]:
    if not settings.SAM_GOV_API_KEY:
        raise IntegrationError("SAM_GOV_API_KEY is not configured.")

    params = _build_sam_params(**filters)
    try:
        response = requests.get(settings.SAM_GOV_BASE_URL, params=params, timeout=30)
    except requests.RequestException as exc:
        raise IntegrationError("SAM.gov could not be reached. Check network access and try again.") from exc

    if response.status_code == 404:
        return {
            "total_records": 0,
            "limit": params["limit"],
            "offset": params["offset"],
            "opportunities": [],
            "persisted": {"enabled": persist, "created": 0, "updated": 0, "errors": []},
        }

    if not response.ok:
        detail = ""
        try:
            payload = response.json()
            detail = _safe_text(payload.get("message") or payload.get("error") or payload.get("detail"), max_length=300)
        except ValueError:
            detail = _safe_text(response.text, max_length=300)
        suffix = f" {detail}" if detail else ""
        raise IntegrationError(f"SAM.gov returned HTTP {response.status_code}.{suffix}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise IntegrationError("SAM.gov returned a response that was not valid JSON.") from exc

    opportunities = payload.get("opportunitiesData", [])
    if not isinstance(opportunities, list):
        opportunities = []

    created = 0
    updated = 0
    persistence_errors: list[str] = []
    if persist:
        for record in opportunities:
            if not isinstance(record, dict):
                continue
            try:
                _, was_created = upsert_sam_opportunity(record)
                created += int(was_created)
                updated += int(not was_created)
            except IntegrationError as exc:
                persistence_errors.append(str(exc))

    normalized_opportunities = []
    for record in opportunities:
        if not isinstance(record, dict):
            continue
        notice_id = _safe_text(record.get("noticeId") or record.get("noticeid"), max_length=255)
        normalized_opportunities.append({
            **record,
            "source_id": notice_id,
            "source_url": f"https://sam.gov/opp/{notice_id}/view" if notice_id else "",
        })

    return {
        "total_records": max(0, _safe_int(payload.get("totalRecords"), 0)),
        "limit": max(1, _safe_int(payload.get("limit"), params["limit"])),
        "offset": max(0, _safe_int(payload.get("offset"), params["offset"])),
        "opportunities": normalized_opportunities,
        "persisted": {
            "enabled": persist,
            "created": created,
            "updated": updated,
            "errors": persistence_errors,
        },
    }


def usaspending_status(*, probe: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "configured": bool(settings.USASPENDING_BASE_URL),
        "base_url": settings.USASPENDING_BASE_URL,
    }
    if not probe:
        return result

    url = f"{settings.USASPENDING_BASE_URL.rstrip('/')}/api/v2/references/agency/"
    try:
        response = requests.get(url, timeout=15)
        result.update({"reachable": response.ok, "status_code": response.status_code})
    except requests.RequestException:
        result.update({"reachable": False, "error": "USAspending could not be reached."})
    return result


def _decimal(value: Any):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _usa_date(value: Any):
    if not value:
        return None
    parsed = parse_date(str(value)[:10])
    return parsed


def _usa_value(record: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def upsert_usaspending_award(record: dict[str, Any], *, award_type: str | None = None):
    from django.db import models
    from .models import Agency, Award, Vendor

    source_id = _safe_text(_usa_value(record, "generated_unique_award_id", "Award ID", "award_id"), max_length=255)
    if not source_id:
        raise IntegrationError("USAspending returned an award without an award ID.")

    recipient = _safe_text(_usa_value(record, "Recipient Name", "recipient_name"), max_length=255)
    recipient_uei = _safe_text(_usa_value(record, "recipient_uei", "Recipient UEI"), max_length=32)
    awarding_agency = _safe_text(_usa_value(record, "Awarding Agency", "awarding_agency_name"), max_length=255)
    funding_agency = _safe_text(_usa_value(record, "Funding Agency", "funding_agency_name"), max_length=255)
    award_number = _safe_text(_usa_value(record, "Award ID", "piid", "award_id"), max_length=160)
    amount = _decimal(_usa_value(record, "Award Amount", "generated_current_total_value", "obligated_amount", default=0))
    potential = _decimal(_usa_value(record, "Potential Award Amount", "generated_potential_total_value", default=0))
    description = _safe_text(_usa_value(record, "Description", "description"))
    naics = _safe_text(_usa_value(record, "NAICS Code", "naics_code"), max_length=12)
    psc = _safe_text(_usa_value(record, "PSC Code", "product_or_service_code"), max_length=12)
    pop = _safe_text(_usa_value(record, "Place of Performance", "place_of_performance"), max_length=500)

    defaults = {
        "source": "usaspending.gov",
        "award_number": award_number,
        "award_type": award_type or Award.AwardType.CONTRACT,
        "description": description,
        "recipient_name": recipient,
        "recipient_uei": recipient_uei,
        "awarding_agency": awarding_agency,
        "funding_agency": funding_agency,
        "obligated_amount": amount,
        "potential_amount": potential,
        "start_date": _usa_date(_usa_value(record, "Start Date", "period_of_performance_start_date")),
        "end_date": _usa_date(_usa_value(record, "End Date", "period_of_performance_current_end_date")),
        "naics_code": naics,
        "psc_code": psc,
        "place_of_performance": pop,
        "source_url": f"https://www.usaspending.gov/award/{source_id}/",
        "raw_data": record,
    }
    award, created = Award.objects.update_or_create(source_id=source_id, defaults=defaults)

    if recipient:
        Vendor.objects.update_or_create(
            name=recipient,
            defaults={
                "uei": recipient_uei,
                "obligated_amount": amount,
                "award_count": Award.objects.filter(recipient_name=recipient).count(),
                "raw_data": {"latest_award": source_id},
            },
        )
    for agency_name in {awarding_agency, funding_agency} - {""}:
        Agency.objects.update_or_create(
            name=agency_name,
            defaults={
                "award_count": Award.objects.filter(
                    models.Q(awarding_agency=agency_name) | models.Q(funding_agency=agency_name)
                ).count(),
                "obligated_amount": Award.objects.filter(awarding_agency=agency_name).aggregate(
                    total=models.Sum("obligated_amount")
                )["total"] or 0,
                "raw_data": {"source": "usaspending.gov"},
            },
        )
    return award, created


def search_usaspending_awards(
    *,
    keyword: str = "",
    recipient: str = "",
    agency: str = "",
    naics: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    limit: int = 25,
    persist: bool = False,
) -> dict[str, Any]:
    today = date.today()
    start_date = start_date or f"{today.year - 1}-01-01"
    end_date = end_date or today.isoformat()
    filters: dict[str, Any] = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": ["A", "B", "C", "D"],
    }
    if keyword:
        filters["keywords"] = [keyword]
    if recipient:
        filters["recipient_search_text"] = [recipient]
    if agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": agency}]
    if naics:
        filters["naics_codes"] = {"require": [naics]}

    payload = {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Award Amount", "Total Outlays", "Description",
            "Start Date", "End Date", "Awarding Agency", "Funding Agency", "Contract Award Type",
            "generated_unique_award_id",
        ],
        "page": max(1, page),
        "limit": max(1, min(limit, 100)),
        "subawards": False,
    }
    url = f"{settings.USASPENDING_BASE_URL.rstrip('/')}/api/v2/search/spending_by_award/"
    try:
        response = requests.post(url, json=payload, timeout=45)
    except requests.RequestException as exc:
        raise IntegrationError("USAspending could not be reached. Check network access and try again.") from exc
    if not response.ok:
        detail = _safe_text(response.text, max_length=400)
        raise IntegrationError(f"USAspending returned HTTP {response.status_code}. {detail}".strip())
    try:
        data = response.json()
    except ValueError as exc:
        raise IntegrationError("USAspending returned invalid JSON.") from exc

    results = data.get("results") if isinstance(data, dict) else []
    if not isinstance(results, list):
        results = []
    created = updated = 0
    errors: list[str] = []
    if persist:
        for record in results:
            if not isinstance(record, dict):
                continue
            try:
                _, was_created = upsert_usaspending_award(record)
                created += int(was_created)
                updated += int(not was_created)
            except IntegrationError as exc:
                errors.append(str(exc))

    return {
        "page_metadata": data.get("page_metadata", {}),
        "spending_level": data.get("spending_level", "awards"),
        "results": results,
        "persisted": {"enabled": persist, "created": created, "updated": updated, "errors": errors},
        "request": {"start_date": start_date, "end_date": end_date, "keyword": keyword, "recipient": recipient, "agency": agency, "naics": naics},
    }




def _grant_source_id(opportunity_id: Any) -> str:
    value = _safe_text(opportunity_id, max_length=220)
    if not value:
        raise IntegrationError("Grants.gov returned an opportunity without an ID.")
    return f"grants.gov:{value}"


def _grant_date(value: Any):
    if not value:
        return None
    raw = str(value).strip()
    from datetime import datetime, time
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y %I:%M:%S %p %Z"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
        except (ValueError, TypeError):
            continue
    parsed = parse_datetime(raw)
    if parsed:
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    parsed_date = parse_date(raw[:10])
    if parsed_date:
        return timezone.make_aware(datetime.combine(parsed_date, time.min))
    return None


def upsert_grants_opportunity(record: dict[str, Any]) -> tuple[Opportunity, bool]:
    opportunity_id = record.get("id") or record.get("opportunityId")
    source_id = _grant_source_id(opportunity_id)
    number = _safe_text(record.get("number") or record.get("opportunityNumber"), max_length=120)
    title = _safe_text(record.get("title") or record.get("opportunityTitle"), max_length=500) or "Untitled Grants.gov opportunity"
    agency = _safe_text(record.get("agencyName") or record.get("owningAgencyCode"), max_length=255)
    agency_code = _safe_text(record.get("agencyCode") or record.get("owningAgencyCode"), max_length=80)
    status_value = _safe_text(record.get("oppStatus"), max_length=80)
    alns = record.get("alnist") or record.get("alns") or []
    aln_values = []
    if isinstance(alns, list):
        for item in alns:
            aln_values.append(str(item.get("alnNumber") or item.get("id") or "") if isinstance(item, dict) else str(item))
    else:
        aln_values = [str(alns)]
    aln_text = ", ".join(v for v in aln_values if v)

    defaults = {
        "source": "grants.gov",
        "solicitation_number": number,
        "title": title,
        "description": _safe_text(record.get("synopsisDesc") or record.get("description")),
        "agency": agency or agency_code,
        "subagency": agency_code,
        "office": "",
        "organization_path": agency,
        "notice_type": Opportunity.NoticeType.OTHER,
        "notice_type_raw": f"Federal Grant - {status_value}"[:120],
        "naics_code": "",
        "psc_code": aln_text[:12],
        "set_aside": "",
        "set_aside_code": "",
        "posted_date": _grant_date(record.get("openDate") or record.get("postingDate")),
        "response_deadline": _grant_date(record.get("closeDate") or record.get("responseDateDesc")),
        "archive_date": None,
        "place_of_performance": "",
        "active": status_value.lower() in {"posted", "forecasted", "open", ""},
        "source_url": f"https://www.grants.gov/search-results-detail/{opportunity_id}",
        "resource_links": [],
        "raw_data": record,
    }
    return Opportunity.objects.update_or_create(source_id=source_id, defaults=defaults)


def search_grants_opportunities(
    *,
    keyword: str = "",
    opportunity_number: str = "",
    agencies: str = "",
    statuses: str = "forecasted|posted",
    aln: str = "",
    funding_categories: str = "",
    eligibilities: str = "",
    funding_instruments: str = "",
    sort_by: str = "",
    limit: int = 25,
    offset: int = 0,
    persist: bool = False,
) -> dict[str, Any]:
    payload = {
        "rows": max(1, min(int(limit), 100)),
        "startRecordNum": max(0, int(offset)),
        "keyword": keyword,
        "oppNum": opportunity_number,
        "agencies": agencies,
        "oppStatuses": statuses,
        "aln": aln,
        "fundingCategories": funding_categories,
        "eligibilities": eligibilities,
        "fundingInstruments": funding_instruments,
        "sortBy": sort_by,
    }
    payload = {key: value for key, value in payload.items() if value not in ("", None)}

    try:
        response = requests.post(f"{settings.GRANTS_GOV_BASE_URL.rstrip('/')}/search2", json=payload, timeout=30)
    except requests.RequestException as exc:
        raise IntegrationError("Grants.gov could not be reached. Check network access and try again.") from exc

    if not response.ok:
        raise IntegrationError(f"Grants.gov returned HTTP {response.status_code}: {_safe_text(response.text, max_length=300)}")

    try:
        body = response.json()
    except ValueError as exc:
        raise IntegrationError("Grants.gov returned a response that was not valid JSON.") from exc

    if body.get("errorcode") not in (0, "0", None):
        raise IntegrationError(_safe_text(body.get("msg") or "Grants.gov search failed.", max_length=300))

    data = body.get("data") or {}
    opportunities = data.get("oppHits") or []
    if not isinstance(opportunities, list):
        opportunities = []

    created = updated = 0
    errors = []
    if persist:
        for record in opportunities:
            if not isinstance(record, dict):
                continue
            try:
                _, was_created = upsert_grants_opportunity(record)
                created += int(was_created)
                updated += int(not was_created)
            except IntegrationError as exc:
                errors.append(str(exc))

    normalized = []
    for record in opportunities:
        if isinstance(record, dict):
            opportunity_id = record.get("id")
            normalized.append({
                **record,
                "source_id": _grant_source_id(opportunity_id),
                "source_url": f"https://www.grants.gov/search-results-detail/{opportunity_id}",
            })

    return {
        "total_records": int(data.get("hitCount") or 0),
        "limit": int((data.get("searchParams") or {}).get("rows") or payload.get("rows") or 25),
        "offset": int(data.get("startRecord") or (data.get("searchParams") or {}).get("startRecordNum") or 0),
        "opportunities": normalized,
        "facets": {
            "statuses": data.get("oppStatusOptions") or [],
            "eligibilities": data.get("eligibilities") or [],
            "funding_categories": data.get("fundingCategories") or [],
            "funding_instruments": data.get("fundingInstruments") or [],
            "agencies": data.get("agencies") or [],
        },
        "persisted": {"enabled": persist, "created": created, "updated": updated, "errors": errors},
    }


def fetch_grants_opportunity(opportunity_id: str, *, persist: bool = True) -> dict[str, Any]:
    """Fetch and normalize a Grants.gov opportunity into a ForgeGov detail workspace."""
    try:
        numeric_id = int(str(opportunity_id).replace("grants.gov:", ""))
        response = requests.post(
            f"{settings.GRANTS_GOV_BASE_URL.rstrip('/')}/fetchOpportunity",
            json={"opportunityId": numeric_id}, timeout=30,
        )
    except ValueError as exc:
        raise IntegrationError("A valid Grants.gov opportunity ID is required.") from exc
    except requests.RequestException as exc:
        raise IntegrationError("Grants.gov could not be reached.") from exc
    if not response.ok:
        raise IntegrationError(f"Grants.gov returned HTTP {response.status_code}: {_safe_text(response.text, max_length=300)}")
    try:
        body = response.json()
    except ValueError as exc:
        raise IntegrationError("Grants.gov returned a response that was not valid JSON.") from exc
    if body.get("errorcode") not in (0, "0", None):
        raise IntegrationError(_safe_text(body.get("msg") or "Grants.gov detail request failed.", max_length=300))

    data = body.get("data") or {}
    synopsis = data.get("synopsis") or {}
    agency_details = data.get("agencyDetails") or synopsis.get("agencyDetails") or {}
    top_agency_details = data.get("topAgencyDetails") or synopsis.get("topAgencyDetails") or {}
    source_url = f"https://www.grants.gov/search-results-detail/{numeric_id}"
    merged = {
        **data, **synopsis,
        "id": data.get("id") or numeric_id,
        "opportunityId": data.get("id") or numeric_id,
        "title": data.get("opportunityTitle") or synopsis.get("opportunityTitle"),
        "number": data.get("opportunityNumber") or synopsis.get("opportunityNumber"),
        "opportunityNumber": data.get("opportunityNumber") or synopsis.get("opportunityNumber"),
        "agencyName": agency_details.get("agencyName") or synopsis.get("agencyName") or top_agency_details.get("agencyName"),
        "agencyCode": agency_details.get("agencyCode") or synopsis.get("agencyCode") or data.get("owningAgencyCode"),
        "openDate": synopsis.get("postingDate") or synopsis.get("postingDateStr"),
        "closeDate": synopsis.get("responseDateDesc") or data.get("originalDueDateDesc"),
        "oppStatus": data.get("oppStatus") or ("forecasted" if data.get("forecast") else "posted"),
        "source_url": source_url,
    }
    source_id = _grant_source_id(numeric_id)
    if persist:
        opportunity, _ = upsert_grants_opportunity(merged)
        merged["forgegov_opportunity_id"] = opportunity.id
        source_id = opportunity.source_id
    merged["source_id"] = source_id

    documents: list[dict[str, Any]] = []
    seen_documents: set[tuple[str, str]] = set()
    def add_document(name: Any, url: Any = "", description: Any = "") -> None:
        document_name = _safe_text(name or description or "Grants.gov document", max_length=500)
        document_url = _safe_text(url, max_length=1500) or source_url
        key = (document_name.lower(), document_url)
        if key in seen_documents: return
        seen_documents.add(key)
        documents.append({
            "name": document_name, "url": document_url,
            "description": _safe_text(description, max_length=1000),
            "preview_available": bool(document_url != source_url and document_url.lower().split("?")[0].endswith((".pdf", ".txt", ".html", ".htm"))),
        })
    for folder in data.get("synopsisAttachmentFolders") or []:
        if not isinstance(folder, dict): continue
        for attachment in folder.get("synopsisAttachments") or []:
            if not isinstance(attachment, dict): continue
            add_document(attachment.get("fileName") or attachment.get("fileDescription") or folder.get("folderName"), attachment.get("downloadUrl") or attachment.get("fileUrl") or attachment.get("url") or attachment.get("attachmentUrl"), attachment.get("fileDescription") or folder.get("folderType") or folder.get("folderName"))
    for document_url in data.get("synopsisDocumentURLs") or []:
        if isinstance(document_url, dict):
            add_document(document_url.get("description") or document_url.get("name") or document_url.get("url"), document_url.get("url") or document_url.get("link") or document_url.get("documentUrl"), document_url.get("description"))
        elif document_url: add_document(document_url, document_url)

    contacts = [{
        "name": _safe_text(synopsis.get("agencyContactName"), max_length=255),
        "email": _safe_text(synopsis.get("agencyContactEmail"), max_length=255),
        "phone": _safe_text(synopsis.get("agencyContactPhone"), max_length=100),
        "description": _safe_text(synopsis.get("agencyContactDesc") or synopsis.get("agencyContactEmailDesc"), max_length=1000),
    }]
    contacts = [contact for contact in contacts if any(contact.values())]
    def normalize_options(values: Any, *, number_key: str = "id") -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in values or []:
            if isinstance(item, dict):
                code = item.get(number_key) or item.get("alnNumber") or item.get("code") or item.get("value") or ""
                label = item.get("description") or item.get("programTitle") or item.get("label") or ""
                normalized.append({"code": _safe_text(code, max_length=120), "label": _safe_text(label, max_length=500)})
            elif item: normalized.append({"code": _safe_text(item, max_length=120), "label": ""})
        return normalized
    return {
        "opportunity": merged,
        "description": _safe_text(synopsis.get("synopsisDesc") or data.get("description"), max_length=50000),
        "documents": documents, "source_url": source_url, "contacts": contacts,
        "eligibilities": normalize_options(synopsis.get("applicantTypes")),
        "funding_instruments": normalize_options(synopsis.get("fundingInstruments")),
        "funding_categories": normalize_options(synopsis.get("fundingActivityCategories")),
        "alns": normalize_options(data.get("alns"), number_key="alnNumber"),
        "award_ceiling": synopsis.get("awardCeilingFormatted") or synopsis.get("awardCeiling"),
        "award_floor": synopsis.get("awardFloorFormatted") or synopsis.get("awardFloor"),
        "cost_sharing": synopsis.get("costSharing"),
    }


SAM_CONTRACT_AWARD_TYPES = {
    "contracts": {"awardOrIDV": "Award"},
    "idv": {"awardOrIDV": "IDV"},
    "vehicles": {"awardOrIDV": "IDV"},
}


def search_sam_contract_awards(
    *,
    record_type: str = "contracts",
    keyword: str = "",
    agency: str = "",
    naics: str = "",
    psc: str = "",
    state: str = "",
    fiscal_year: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Search SAM.gov Contract Awards using the same server-side SAM API key."""
    if not settings.SAM_GOV_API_KEY:
        raise IntegrationError("SAM_GOV_API_KEY is not configured.")
    if record_type not in SAM_CONTRACT_AWARD_TYPES:
        raise IntegrationError("record_type must be contracts, idv, or vehicles.")

    params: dict[str, Any] = {
        "api_key": settings.SAM_GOV_API_KEY,
        "limit": max(1, min(limit, 100)),
        "offset": max(0, offset),
        "includeSections": "contractId,coreData,awardDetails,awardeeData",
        **SAM_CONTRACT_AWARD_TYPES[record_type],
    }
    optional = {
        "q": keyword,
        "contractingDepartmentName": agency,
        "naicsCode": naics,
        "productOrServiceCode": psc,
        "placeOfPerformStateCode": state,
        "fiscalYear": fiscal_year,
    }
    params.update({key: value for key, value in optional.items() if value})

    try:
        response = requests.get(settings.SAM_CONTRACT_AWARDS_BASE_URL, params=params, timeout=45)
    except requests.RequestException as exc:
        raise IntegrationError("SAM.gov Contract Awards could not be reached.") from exc
    if response.status_code == 204:
        return {"total_records": 0, "limit": params["limit"], "offset": params["offset"], "results": []}
    if not response.ok:
        raise IntegrationError(f"SAM.gov Contract Awards returned HTTP {response.status_code}. {_safe_text(response.text, max_length=400)}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise IntegrationError("SAM.gov Contract Awards returned invalid JSON.") from exc

    records = payload.get("awardSummary") or payload.get("results") or []
    if not isinstance(records, list):
        records = []

    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        contract_id = record.get("contractId") or {}
        core = record.get("coreData") or {}
        details = record.get("awardDetails") or {}
        awardee = details.get("awardeeData") or record.get("awardeeData") or {}
        header = awardee.get("awardeeHeader") or {}
        award_type = core.get("awardOrIDVType") or {}
        contracting = (core.get("federalOrganization") or {}).get("contractingInformation") or {}
        department = contracting.get("contractingDepartment") or {}
        normalized.append({
            "piid": contract_id.get("piid", ""),
            "modification_number": contract_id.get("modificationNumber", ""),
            "referenced_idv": contract_id.get("referencedIDVPiid", ""),
            "award_or_idv": core.get("awardOrIDV", ""),
            "award_type": award_type.get("name", "") if isinstance(award_type, dict) else award_type,
            "title": core.get("title", "") or details.get("descriptionOfContractRequirement", ""),
            "recipient_name": header.get("awardeeName", "") if isinstance(header, dict) else "",
            "awarding_agency": department.get("name", "") if isinstance(department, dict) else "",
            "date_signed": core.get("dateSigned", "") or details.get("dateSigned", ""),
            "dollars_obligated": details.get("dollarsObligated", 0),
            "potential_amount": details.get("totalDollarsObligated", 0),
            "raw_data": record,
        })
    total = payload.get("totalRecords") or payload.get("total_records") or len(normalized)
    return {"total_records": _safe_int(total, len(normalized)), "limit": params["limit"], "offset": params["offset"], "results": normalized}


def _clean_attachment_name(name: Any, url: Any = "", *, fallback: str = "Government attachment") -> str:
    from urllib.parse import unquote, urlparse
    import re

    raw = _safe_text(name, max_length=500).strip()
    parsed_name = unquote(urlparse(str(url or "")).path.rsplit("/", 1)[-1]).strip()
    candidates = [raw, parsed_name]
    chosen = next((value for value in candidates if value and value.lower() not in {"download", "attachment", "file"}), fallback)
    chosen = unquote(chosen).replace("+", " ")
    chosen = re.sub(r"[\r\n\t]+", " ", chosen)
    chosen = re.sub(r"\s{2,}", " ", chosen).strip(" ._-")
    if not chosen:
        chosen = fallback
    return chosen[:500]


def fetch_sam_opportunity_documents(notice_id: str) -> dict[str, Any]:
    """Return public SAM attachment metadata and fetch the protected description when available."""
    if not settings.SAM_GOV_API_KEY:
        raise IntegrationError("SAM_GOV_API_KEY is not configured.")
    opportunity = Opportunity.objects.filter(source_id=notice_id).first()
    if not opportunity:
        data = search_sam_opportunities(notice_id=notice_id, limit=1, persist=True)
        opportunity = Opportunity.objects.filter(source_id=notice_id).first()
        if not opportunity and not data.get("opportunities"):
            raise IntegrationError("The SAM.gov opportunity could not be found.")
    raw = opportunity.raw_data if opportunity else {}
    description_url = raw.get("description") or raw.get("descriptionUrl") or raw.get("descriptionURL")
    description = opportunity.description if opportunity else ""
    if isinstance(description_url, str) and description_url.startswith("http"):
        try:
            response = requests.get(description_url, params={"api_key": settings.SAM_GOV_API_KEY}, timeout=30)
            if response.ok:
                try:
                    body = response.json()
                    description = body.get("description") or body.get("content") or body.get("text") or description
                except ValueError:
                    description = response.text or description
        except requests.RequestException:
            pass
    links = opportunity.resource_links if opportunity else raw.get("resourceLinks", [])
    documents = []
    for index, link in enumerate(links if isinstance(links, list) else []):
        if isinstance(link, dict):
            url = link.get("url") or link.get("link") or link.get("href") or ""
            name = link.get("name") or link.get("title") or link.get("filename") or link.get("description")
        else:
            url, name = str(link), ""
        if url:
            clean_name = _clean_attachment_name(name, url, fallback=f"Solicitation attachment {index + 1}")
            documents.append({"name": clean_name, "url": url, "source": "sam.gov", "preview_available": url.lower().split("?", 1)[0].endswith((".pdf", ".txt", ".html", ".htm"))})
    return {"notice_id": notice_id, "description": description, "documents": documents, "source_url": opportunity.source_url if opportunity else ""}


USASPENDING_IDV_CODES = ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]


def search_usaspending_contract_vehicles(
    *,
    keyword: str = "",
    recipient: str = "",
    agency: str = "",
    naics: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    limit: int = 25,
    persist: bool = False,
) -> dict[str, Any]:
    """Search public USAspending IDV records used as federal contract vehicles."""
    today = date.today()
    start_date = start_date or f"{today.year - 5}-01-01"
    end_date = end_date or today.isoformat()
    filters: dict[str, Any] = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": USASPENDING_IDV_CODES,
    }
    if keyword:
        filters["keywords"] = [keyword]
    if recipient:
        filters["recipient_search_text"] = [recipient]
    if agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": agency}]
    if naics:
        filters["naics_codes"] = {"require": [naics]}

    payload = {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Award Amount", "Potential Award Amount", "Description",
            "Start Date", "End Date", "Awarding Agency", "Funding Agency", "Award Type",
            "generated_unique_award_id",
        ],
        "page": max(1, page),
        "limit": max(1, min(limit, 100)),
        "subawards": False,
    }
    url = f"{settings.USASPENDING_BASE_URL.rstrip('/')}/api/v2/search/spending_by_award/"
    try:
        response = requests.post(url, json=payload, timeout=45)
    except requests.RequestException as exc:
        raise IntegrationError("USAspending contract vehicle search could not be reached.") from exc
    if not response.ok:
        raise IntegrationError(f"USAspending returned HTTP {response.status_code}. {_safe_text(response.text, max_length=400)}")
    try:
        data = response.json()
    except ValueError as exc:
        raise IntegrationError("USAspending returned invalid JSON for contract vehicles.") from exc

    results = data.get("results") if isinstance(data, dict) else []
    if not isinstance(results, list):
        results = []
    created = updated = 0
    errors: list[str] = []
    if persist:
        from .models import Award
        for record in results:
            if not isinstance(record, dict):
                continue
            try:
                _, was_created = upsert_usaspending_award(record, award_type=Award.AwardType.VEHICLE)
                created += int(was_created)
                updated += int(not was_created)
            except IntegrationError as exc:
                errors.append(str(exc))
    return {
        "page_metadata": data.get("page_metadata", {}),
        "results": results,
        "persisted": {"enabled": persist, "created": created, "updated": updated, "errors": errors},
        "request": {"start_date": start_date, "end_date": end_date, "keyword": keyword, "recipient": recipient, "agency": agency, "naics": naics},
    }


def fetch_sam_opportunity_detail(notice_id: str) -> dict[str, Any]:
    """Return one normalized SAM opportunity, public documents, and evidence-based incumbent signals."""
    result = search_sam_opportunities(notice_id=notice_id, limit=1, persist=True)
    records = result.get("opportunities") or []
    if not records:
        raise IntegrationError("The SAM.gov opportunity could not be found.")
    documents = fetch_sam_opportunity_documents(notice_id)
    record = records[0]

    # SAM opportunities do not normally identify a confirmed incumbent. These signals
    # rank recent stored awardees that match the opportunity's agency and/or NAICS.
    from django.db.models import Count, Max, Q, Sum
    from .models import Award
    agency = _safe_text(record.get("fullParentPathName") or record.get("department") or record.get("subTier"), max_length=255)
    naics = _safe_text(record.get("naicsCode"), max_length=12)
    candidates = Award.objects.exclude(recipient_name="")
    evidence = Q()
    if agency:
        evidence |= Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency)
        # Parent paths can be much longer than the stored top-tier agency name.
        agency_parts = [part.strip() for part in agency.split(".") if len(part.strip()) > 4]
        for part in agency_parts[-3:]:
            evidence |= Q(awarding_agency__icontains=part) | Q(funding_agency__icontains=part)
    if naics:
        evidence |= Q(naics_code=naics)
    signals = []
    if evidence:
        signals = list(
            candidates.filter(evidence)
            .values("recipient_name", "recipient_uei")
            .annotate(award_count=Count("id"), obligated=Sum("obligated_amount"), latest_end=Max("end_date"))
            .order_by("-award_count", "-obligated")[:8]
        )

    return {
        "opportunity": record,
        "description": documents.get("description", ""),
        "documents": documents.get("documents", []),
        "source_url": documents.get("source_url") or record.get("source_url", ""),
        "incumbent_signals": signals,
        "incumbent_signal_note": "Candidates are inferred from stored award history matching the agency or NAICS and are not confirmed incumbents.",
    }


FORECAST_FALLBACK = [
    {
        "agency": "Federal acquisition forecast directory",
        "forecast_url": "https://www.acquisition.gov/procurement-forecasts",
        "agency_url": "https://www.acquisition.gov/",
        "source": "Acquisition.gov",
    }
]


def search_federal_forecast_sources(*, query: str = "") -> dict[str, Any]:
    """Read the official Acquisition.gov directory of recurring agency procurement forecasts."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    directory_url = "https://www.acquisition.gov/procurement-forecasts"
    try:
        response = requests.get(directory_url, timeout=30, headers={"User-Agent": "ForgeGov/1.2 (+https://forgegov.com)"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        rows: list[dict[str, str]] = []
        for tr in soup.select("table tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            agency_link = cells[0].find("a")
            forecast_link = cells[1].find("a")
            agency = cells[0].get_text(" ", strip=True)
            forecast_url = urljoin(directory_url, forecast_link.get("href", "")) if forecast_link else ""
            agency_url = urljoin(directory_url, agency_link.get("href", "")) if agency_link else ""
            # Acquisition.gov occasionally publishes stale or malformed agency links.
            # Keep cards usable by falling back to the agency site or directory.
            if not forecast_url.startswith(("http://", "https://")):
                forecast_url = agency_url or directory_url
            if "international development" in agency.lower() and "usaid.gov" not in forecast_url.lower():
                forecast_url = "https://www.usaid.gov/work-usaid/business-forecast"
            if agency and forecast_url:
                rows.append({
                    "agency": agency,
                    "forecast_url": forecast_url,
                    "agency_url": agency_url,
                    "source": "Acquisition.gov",
                })
        sources = rows or FORECAST_FALLBACK
        reachable = True
    except (requests.RequestException, ValueError):
        sources = FORECAST_FALLBACK
        reachable = False
    term = query.strip().lower()
    if term:
        sources = [item for item in sources if term in item["agency"].lower()]
    return {
        "total_records": len(sources),
        "results": sources,
        "directory_url": directory_url,
        "reachable": reachable,
    }


STATE_LOCAL_SOURCE_DIRECTORY = [
    {"jurisdiction": "National state procurement directory", "state": "US", "portal": "https://www.naspo.org/research-and-innovation/rosp-category/procurement-website/", "coverage": "Official state procurement websites"},
    {"jurisdiction": "California", "state": "CA", "portal": "https://caleprocure.ca.gov/pages/index.aspx", "coverage": "State solicitations and bid events"},
    {"jurisdiction": "Texas", "state": "TX", "portal": "https://www.txsmartbuy.gov/esbd", "coverage": "Electronic State Business Daily"},
    {"jurisdiction": "Virginia", "state": "VA", "portal": "https://eva.virginia.gov/", "coverage": "State and participating local opportunities"},
    {"jurisdiction": "Maryland", "state": "MD", "portal": "https://emma.maryland.gov/", "coverage": "State procurement opportunities"},
    {"jurisdiction": "New York", "state": "NY", "portal": "https://www.nyscr.ny.gov/home/contracts", "coverage": "New York State Contract Reporter"},
    {"jurisdiction": "Florida", "state": "FL", "portal": "https://vendor.myfloridamarketplace.com/", "coverage": "State bid advertisements"},
    {"jurisdiction": "North Carolina", "state": "NC", "portal": "https://evp.nc.gov/", "coverage": "Electronic Vendor Portal"},
    {"jurisdiction": "Washington", "state": "WA", "portal": "https://pr-webs-vendor.des.wa.gov/bidcalendar.aspx", "coverage": "Washington Electronic Business Solution"},
    {"jurisdiction": "Georgia", "state": "GA", "portal": "https://www.doas.ga.gov/state-purchasing/bids-and-contracts", "coverage": "Georgia Procurement Registry"},
]


def search_state_local_sources(*, query: str = "", state: str = "") -> dict[str, Any]:
    term = query.strip().lower()
    state_code = state.strip().upper()
    results = STATE_LOCAL_SOURCE_DIRECTORY
    if term:
        results = [r for r in results if term in r["jurisdiction"].lower() or term in r["coverage"].lower()]
    if state_code:
        results = [r for r in results if r["state"] == state_code]
    return {"total_records": len(results), "results": results, "source": "Official procurement portals"}


def search_sam_subawards(
    *,
    piid: str = "",
    referenced_idv: str = "",
    agency_id: str = "",
    from_date: str = "",
    to_date: str = "",
    page: int = 0,
    limit: int = 25,
) -> dict[str, Any]:
    """Search the public SAM Acquisition Subaward Reporting API."""
    if not settings.SAM_GOV_API_KEY:
        raise IntegrationError("SAM_GOV_API_KEY is not configured.")
    today = date.today()
    params: dict[str, Any] = {
        "api_key": settings.SAM_GOV_API_KEY,
        "pageNumber": max(0, page),
        "pageSize": max(1, min(limit, 1000)),
        "status": "Published",
        "fromDate": from_date or (today - timedelta(days=365)).isoformat(),
        "toDate": to_date or today.isoformat(),
    }
    optional = {"piid": piid, "referencedIDVPIID": referenced_idv, "agencyId": agency_id}
    params.update({k: v for k, v in optional.items() if v})
    try:
        response = requests.get(settings.SAM_SUBAWARDS_BASE_URL, params=params, timeout=45)
    except requests.RequestException as exc:
        raise IntegrationError("SAM.gov subaward reporting could not be reached.") from exc
    if not response.ok:
        raise IntegrationError(f"SAM.gov subaward reporting returned HTTP {response.status_code}. {_safe_text(response.text, max_length=400)}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise IntegrationError("SAM.gov subaward reporting returned invalid JSON.") from exc
    records = payload.get("data") or []
    if not isinstance(records, list):
        records = []
    normalized = []
    for row in records:
        if not isinstance(row, dict):
            continue
        sub_naics = row.get("subContractorNaics") or {}
        if not isinstance(sub_naics, dict):
            sub_naics = {}
        address = row.get("entityPhysicalAddress") or {}
        if not isinstance(address, dict):
            address = {}
        state_value = address.get("state") or {}
        if isinstance(state_value, dict):
            state_label = state_value.get("code") or state_value.get("name") or ""
        else:
            state_label = str(state_value or "")
        place_parts = [str(address.get("city") or "").strip(), str(state_label).strip()]
        place_of_performance = ", ".join(part for part in place_parts if part)
        business_types = row.get("subEntityBusinessTypes") or row.get("subBusinessTypes") or []
        normalized.append({
            "piid": row.get("piid") or row.get("primeAwardPIID") or "",
            "referenced_idv": row.get("referencedIDVPIID") or "",
            "prime_contractor": row.get("primeEntityName") or row.get("primeAwardeeName") or row.get("primeRecipientName") or "",
            "subcontractor": row.get("subEntityLegalBusinessName") or row.get("subAwardeeName") or row.get("subawardeeName") or row.get("subcontractorName") or "",
            "amount": row.get("subAwardAmount") or row.get("subawardAmount") or 0,
            "description": row.get("subAwardDescription") or row.get("descriptionOfRequirement") or "",
            "action_date": row.get("subAwardDate") or row.get("subAwardActionDate") or row.get("actionDate") or "",
            "place_of_performance": place_of_performance or row.get("subAwardPlaceOfPerformanceCity") or row.get("placeOfPerformanceCity") or "",
            "naics": sub_naics.get("code") or row.get("naicsCode") or "",
            "sub_entity_uei": row.get("subEntityUei") or row.get("subEntityUEI") or "",
            "prime_entity_uei": row.get("primeEntityUei") or row.get("primeEntityUEI") or "",
            "sub_business_types": business_types if isinstance(business_types, list) else [],
            "raw_data": row,
        })
    return {
        "total_records": _safe_int(payload.get("totalRecords"), len(normalized)),
        "total_pages": _safe_int(payload.get("totalPages"), 1),
        "page": _safe_int(payload.get("pageNumber"), params["pageNumber"]),
        "limit": params["pageSize"],
        "results": normalized,
    }


def search_sba_subnet_opportunities(*, query: str = "", state: str = "", page: int = 0, page_size: int = 20) -> dict[str, Any]:
    """Read current SBA SUBNet listings with direct, indexed, cached, and persisted fallbacks."""
    from bs4 import BeautifulSoup
    from django.core.cache import cache
    from hashlib import sha1
    from urllib.parse import urljoin
    import time

    page=max(0,page); page_size=min(max(int(page_size or 20), 1), 100); normalized_query=query.strip().lower(); normalized_state=state.strip().lower()
    params={"combine":query,"field_state_value":state or "All","keyword":query,"state":state or "All","page":page,"page_size":page_size,"items_per_page":page_size,"limit":page_size}
    cache_key=f"sba-subnet:v4:{normalized_query}:{normalized_state}:{page}:{page_size}"; snapshot_key=f"sba-subnet:v4:last-good:{page}:{page_size}"
    # SBA's current public listings remain available on its official legacy host.
    # Keep that URL first even when an existing .env still contains the prior www.sba.gov URL.
    official_listing_url = "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities"
    official_landing_url = "https://subnet.sba.gov/client/dsp_Landing.cfm"
    source_urls=[]
    for candidate in (
        official_listing_url,
        getattr(settings,"SBA_SUBNET_URL",""),
        getattr(settings,"SBA_SUBNET_FALLBACK_URL",""),
        official_landing_url,
    ):
        candidate=str(candidate or "").strip()
        if candidate and candidate not in source_urls: source_urls.append(candidate)
    headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ForgeGov/2.5.0","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"en-US,en;q=0.9","Cache-Control":"no-cache"}

    def parse_page(html:str,response_url:str)->tuple[list[dict[str,Any]],bool]:
        soup=BeautifulSoup(html,"html.parser"); results=[]
        for row in soup.select("table tbody tr"):
            cells=row.find_all("td")
            if len(cells)<5: continue
            title_cell=cells[0]; link=title_cell.find("a"); title=link.get_text(" ",strip=True) if link else ""
            if not title: continue
            pieces=[piece.strip() for piece in title_cell.stripped_strings if piece.strip()]
            if pieces and pieces[0]==title: pieces=pieces[1:]
            prime=pieces[0] if len(pieces)>1 else ""
            description=" ".join(pieces[1:]) if len(pieces)>1 else (pieces[0] if pieces else "")
            values=[cell.get_text(" ",strip=True) for cell in cells]; href=urljoin(response_url,link.get("href", "")) if link else response_url
            identity=sha1(f"{href}|{title}".encode()).hexdigest()[:20]
            results.append({"source_id":f"sba-subnet:{identity}","title":title,"prime_contractor":prime,"description":description,"closing_date":values[1] if len(values)>1 else "","performance_start":values[2] if len(values)>2 else "","place_of_performance":values[3] if len(values)>3 else "","naics":values[4] if len(values)>4 else "","point_of_contact":values[5] if len(values)>5 else "","source_url":href})
        if not results:
            labels={"closing date":"closing_date","performance start date":"performance_start","performance start":"performance_start","place of performance":"place_of_performance","naics code":"naics","point of contact":"point_of_contact"}
            for row in soup.select(".views-row"):
                link=row.select_one("h2 a, h3 a, .views-field-title a")
                if not link: continue
                title=link.get_text(" ",strip=True); href=urljoin(response_url,link.get("href", "")); strings=[x.strip() for x in row.stripped_strings if x.strip()]
                if title in strings: strings.remove(title)
                positions=[]
                for i,piece in enumerate(strings):
                    key=piece.rstrip(":").strip().lower()
                    if key in labels: positions.append((i,key))
                first=positions[0][0] if positions else len(strings); intro=strings[:first]; prime=intro[0] if intro else ""; description=" ".join(intro[1:]) if len(intro)>1 else ""; values={}
                for pos,(i,key) in enumerate(positions):
                    nxt=positions[pos+1][0] if pos+1<len(positions) else len(strings); values[labels[key]]=" ".join(strings[i+1:nxt]).strip()
                identity=sha1(f"{href}|{title}".encode()).hexdigest()[:20]
                results.append({"source_id":f"sba-subnet:{identity}","title":title,"prime_contractor":prime,"description":description[:4000],"closing_date":values.get("closing_date",""),"performance_start":values.get("performance_start",""),"place_of_performance":values.get("place_of_performance",""),"naics":values.get("naics",""),"point_of_contact":values.get("point_of_contact",""),"source_url":href or response_url})
        pager=soup.select("nav.pager a, ul.pagination a, .pager a"); has_next=any("next" in (a.get_text(" ",strip=True)+" "+" ".join(a.get("rel",[]))).lower() for a in pager)
        return results,has_next

    def matches(row):
        searchable=" ".join(str(row.get(k) or "") for k in ("title","prime_contractor","description","naics")).lower(); place=str(row.get("place_of_performance") or "").lower()
        return (not normalized_query or normalized_query in searchable) and (not normalized_state or normalized_state=="all" or normalized_state in place)

    def persist(rows):
        for row in rows:
            source_id=_safe_text(row.get("source_id"),max_length=255)
            if not source_id: continue
            naics="".join(c for c in _safe_text(row.get("naics"),max_length=120) if c.isdigit())[:6]; closing=_grant_date(row.get("closing_date"))
            Opportunity.objects.update_or_create(source_id=source_id,defaults={"source":"sba-subnet","title":_safe_text(row.get("title"),max_length=500) or "Untitled SBA SUBNet opportunity","description":_safe_text(row.get("description"),max_length=50000),"agency":_safe_text(row.get("prime_contractor"),max_length=255),"office":"SBA SUBNet","notice_type":Opportunity.NoticeType.OTHER,"notice_type_raw":"Subcontracting Opportunity","naics_code":naics,"response_deadline":closing,"place_of_performance":_safe_text(row.get("place_of_performance"),max_length=500),"active":not closing or closing>=timezone.now(),"source_url":_safe_text(row.get("source_url"),max_length=1500),"raw_data":row})

    def database_snapshot():
        rows=[]
        for op in Opportunity.objects.filter(source="sba-subnet",active=True).order_by("response_deadline","-updated_at")[:250]:
            raw=op.raw_data if isinstance(op.raw_data,dict) else {}; row={"source_id":op.source_id,"title":op.title,"prime_contractor":raw.get("prime_contractor") or op.agency,"description":op.description,"closing_date":raw.get("closing_date") or (op.response_deadline.date().isoformat() if op.response_deadline else ""),"performance_start":raw.get("performance_start") or "","place_of_performance":op.place_of_performance,"naics":raw.get("naics") or op.naics_code,"point_of_contact":raw.get("point_of_contact") or "","source_url":op.source_url}
            if matches(row): rows.append(row)
        start=page*page_size; sliced=rows[start:start+page_size+1]; return sliced[:page_size],len(sliced)>page_size

    # SBA controls its own page size (currently about 10). ForgeGov combines two official
    # source pages into one 20-record application page and deduplicates results.
    for source_index,source_url in enumerate(source_urls):
        try:
            combined=[]; any_next=False; response_url=source_url
            source_pages=[page*2,page*2+1] if "sba.gov/federal-contracting" in source_url else [page]
            for source_page in source_pages:
                source_params=dict(params); source_params["page"]=source_page
                response=requests.get(source_url,params=source_params,timeout=18,headers=headers,allow_redirects=True)
                response.raise_for_status(); response_url=response.url
                parsed,source_has_next=parse_page(response.text,response.url)
                combined.extend(parsed); any_next=any_next or source_has_next
            deduped=[]; seen=set()
            for row in combined:
                key=row.get("source_id") or row.get("source_url") or row.get("title")
                if key in seen: continue
                seen.add(key); deduped.append(row)
            if deduped: persist(deduped)
            results=[row for row in deduped if matches(row)]
            if not combined: raise IntegrationError("SBA returned a page without SUBNet listings.")
            payload={"total_records":None,"page_size":page_size,"results":results[:page_size],"source_url":response_url,"source_name":"SBA SUBNet live directory" if source_index==0 else "Official SBA fallback","page":page,"has_next":any_next or len(results)>=page_size,"status":"live","reachable":True,"warning":""}
            cache.set(cache_key,payload,43200)
            if not normalized_query and normalized_state in {"","all"}: cache.set(snapshot_key,payload,172800)
            return payload
        except (requests.RequestException,IntegrationError):
            continue

    searx=str(getattr(settings,"SEARXNG_URL","") or "").strip()
    if searx and bool(getattr(settings,"AI_WEB_SEARCH_ENABLED",True)):
        terms=['site:sba.gov/opportunity "subcontracting opportunity"']
        if query.strip(): terms.append(query.strip())
        if state.strip() and state.strip().lower()!="all": terms.append(state.strip())
        try:
            wr=requests.get(searx.rstrip("/")+"/search",params={"q":" ".join(terms),"format":"json","language":"en-US","safesearch":1},timeout=18,headers={"User-Agent":"ForgeGov/2.5.0"}); wr.raise_for_status(); rows=wr.json().get("results"); indexed=[]
            if isinstance(rows,list):
                for row in rows:
                    if not isinstance(row,dict): continue
                    href=_safe_text(row.get("url"),max_length=1500); title=_safe_text(row.get("title"),max_length=500)
                    if "sba.gov/opportunity/" not in href.lower() or not title: continue
                    identity=sha1(f"{href}|{title}".encode()).hexdigest()[:20]
                    indexed.append({"source_id":f"sba-subnet:{identity}","title":title,"prime_contractor":"","description":_safe_text(row.get("content"),max_length=4000),"closing_date":"","performance_start":"","place_of_performance":state.strip(),"naics":"","point_of_contact":"","source_url":href})
                    if len(indexed)>=page_size * (page + 1): break
            if indexed:
                persist(indexed)
                start = page * page_size
                page_rows = indexed[start:start + page_size]
                return {"total_records":len(indexed),"page_size":page_size,"results":page_rows,"source_url":str(getattr(settings,"SBA_SUBNET_URL","") or ""),"source_name":"SBA opportunity web index","page":page,"has_next":len(indexed) > start + page_size,"status":"indexed","reachable":False,"warning":"Direct SBA directory access is reconnecting. Showing official SBA opportunity pages discovered through live web search."}
        except (requests.RequestException,ValueError,AttributeError): pass

    cached=cache.get(cache_key) or cache.get(snapshot_key)
    if cached:
        results=[row for row in list(cached.get("results") or []) if matches(row)]; return {**cached,"total_records":len(results),"results":results,"status":"cached","reachable":False,"warning":"Live SBA access is reconnecting. Showing the latest verified SUBNet snapshot."}
    stored,has_next=database_snapshot()
    if stored:
        return {"total_records":len(stored),"results":stored,"source_url":str(getattr(settings,"SBA_SUBNET_URL","") or ""),"source_name":"ForgeGov verified SBA history","page":page,"has_next":has_next,"status":"cached","reachable":False,"warning":"Live SBA access is reconnecting. Showing verified SUBNet opportunities previously retrieved by ForgeGov."}
    return {"total_records":0,"results":[],"source_url":str(getattr(settings,"SBA_SUBNET_URL","") or ""),"source_name":"SBA SUBNet","page":page,"has_next":False,"status":"unavailable","reachable":False,"warning":"Live SBA access is reconnecting. ForgeGov will retry automatically."}
