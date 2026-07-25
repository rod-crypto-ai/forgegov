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


def _safe_text(value: Any, *, max_length: int | None = None) -> str:
    text = "" if value is None else str(value).strip()
    return text[:max_length] if max_length else text


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
    source_url = _safe_text(record.get("uiLink"), max_length=2000) or f"https://sam.gov/opp/{notice_id}/view"
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
        "postedFrom": posted_from or (today - timedelta(days=30)).strftime("%m/%d/%Y"),
        "postedTo": posted_to or today.strftime("%m/%d/%Y"),
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

    return {
        "total_records": payload.get("totalRecords", 0),
        "limit": payload.get("limit", params["limit"]),
        "offset": payload.get("offset", params["offset"]),
        "opportunities": opportunities,
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


def upsert_usaspending_award(record: dict[str, Any]):
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
        "award_type": Award.AwardType.CONTRACT,
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


GRANTS_GOV_SEARCH_URL = "https://api.grants.gov/v1/api/search2"
GRANTS_GOV_DETAIL_URL = "https://api.grants.gov/v1/api/fetchOpportunity"


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
        response = requests.post(GRANTS_GOV_SEARCH_URL, json=payload, timeout=30)
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
    try:
        numeric_id = int(opportunity_id)
        response = requests.post(GRANTS_GOV_DETAIL_URL, json={"opportunityId": numeric_id}, timeout=30)
    except ValueError as exc:
        raise IntegrationError("A valid Grants.gov opportunity ID is required.") from exc
    except requests.RequestException as exc:
        raise IntegrationError("Grants.gov could not be reached.") from exc

    if not response.ok:
        raise IntegrationError(f"Grants.gov returned HTTP {response.status_code}: {_safe_text(response.text, max_length=300)}")

    body = response.json()
    if body.get("errorcode") not in (0, "0", None):
        raise IntegrationError(_safe_text(body.get("msg") or "Grants.gov detail request failed.", max_length=300))

    data = body.get("data") or {}
    synopsis = data.get("synopsis") or {}
    merged = {
        **data,
        **synopsis,
        "id": data.get("id") or numeric_id,
        "title": data.get("opportunityTitle"),
        "number": data.get("opportunityNumber"),
        "agencyName": (data.get("agencyDetails") or {}).get("agencyName") or synopsis.get("agencyName"),
        "openDate": synopsis.get("postingDate"),
        "closeDate": synopsis.get("responseDateDesc"),
        "oppStatus": "posted",
    }
    if persist:
        opportunity, _ = upsert_grants_opportunity(merged)
        merged["forgegov_opportunity_id"] = opportunity.id
        merged["source_id"] = opportunity.source_id
    return merged
