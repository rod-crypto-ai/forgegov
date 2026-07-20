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
