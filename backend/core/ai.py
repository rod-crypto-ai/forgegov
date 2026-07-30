from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import requests
from django.conf import settings
from django.db.models import F

from .models import Award, Contact, FileRecord, Opportunity, PipelineItem, Pursuit, Task


class OpenAIIntegrationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GroundingSource:
    label: str
    source_type: str
    title: str
    url: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "label": self.label,
            "type": self.source_type,
            "title": self.title,
            "url": self.url,
        }


def _text(value: Any, limit: int = 1200) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()[:limit]


def _iso(value: Any) -> str:
    return value.isoformat() if value else ""


def _record_line(label: str, payload: dict[str, Any]) -> str:
    return f"{label} {json.dumps(payload, default=str, ensure_ascii=True)}"


def build_grounding_context(organization) -> tuple[str, list[GroundingSource]]:
    """Build a bounded, tenant-safe snapshot for one AI request."""

    lines: list[str] = []
    sources: list[GroundingSource] = []

    opportunities = Opportunity.objects.filter(active=True).order_by(F("posted_date").desc(nulls_last=True), "response_deadline")[:12]
    for index, record in enumerate(opportunities, start=1):
        label = f"[OPP-{index}]"
        lines.append(_record_line(label, {
            "title": _text(record.title, 500),
            "solicitation_number": record.solicitation_number,
            "agency": record.agency,
            "office": record.office,
            "notice_type": record.notice_type_raw or record.notice_type,
            "naics": record.naics_code,
            "psc": record.psc_code,
            "set_aside": record.set_aside,
            "posted_date": _iso(record.posted_date),
            "response_deadline": _iso(record.response_deadline),
            "place_of_performance": record.place_of_performance,
            "source": record.source,
            "url": record.source_url,
        }))
        sources.append(GroundingSource(label, "opportunity", record.title, record.source_url))

    pipeline_items = (
        PipelineItem.objects.filter(organization=organization)
        .select_related("opportunity")
        .order_by("-updated_at")[:10]
    )
    for index, record in enumerate(pipeline_items, start=1):
        label = f"[PIPE-{index}]"
        title = record.opportunity.title
        lines.append(_record_line(label, {
            "title": _text(title, 500),
            "stage": record.stage,
            "estimated_value": record.estimated_value,
            "probability_of_win": record.probability_of_win,
            "next_action": _text(record.next_action, 500),
            "notes": _text(record.notes),
            "response_deadline": _iso(record.opportunity.response_deadline),
            "source_url": record.opportunity.source_url,
        }))
        sources.append(GroundingSource(label, "pipeline", title, record.opportunity.source_url))

    pursuits = Pursuit.objects.filter(organization=organization).order_by("-updated_at")[:10]
    for index, record in enumerate(pursuits, start=1):
        label = f"[PURSUIT-{index}]"
        lines.append(_record_line(label, {
            "title": _text(record.title, 500),
            "stage": record.stage,
            "estimated_value": record.estimated_value,
            "probability_of_win": record.probability_of_win,
            "due_date": _iso(record.due_date),
            "incumbent": record.incumbent,
            "prime_or_sub": record.prime_or_sub,
            "next_action": _text(record.next_action, 500),
            "notes": _text(record.notes),
        }))
        sources.append(GroundingSource(label, "pursuit", record.title))

    tasks = Task.objects.filter(organization=organization).order_by("completed", "due_at", "-updated_at")[:12]
    for index, record in enumerate(tasks, start=1):
        label = f"[TASK-{index}]"
        lines.append(_record_line(label, {
            "title": _text(record.title, 255),
            "description": _text(record.description),
            "due_at": _iso(record.due_at),
            "completed": record.completed,
        }))
        sources.append(GroundingSource(label, "task", record.title))

    awards = Award.objects.order_by("-updated_at", "-obligated_amount")[:10]
    for index, record in enumerate(awards, start=1):
        label = f"[AWARD-{index}]"
        title = record.award_number or record.source_id
        lines.append(_record_line(label, {
            "award_number": record.award_number,
            "recipient": record.recipient_name,
            "awarding_agency": record.awarding_agency,
            "funding_agency": record.funding_agency,
            "obligated_amount": record.obligated_amount,
            "potential_amount": record.potential_amount,
            "description": _text(record.description),
            "start_date": _iso(record.start_date),
            "end_date": _iso(record.end_date),
            "naics": record.naics_code,
            "psc": record.psc_code,
            "url": record.source_url,
        }))
        sources.append(GroundingSource(label, "award", title, record.source_url))

    contacts = Contact.objects.filter(organization=organization).order_by("-updated_at")[:8]
    for index, record in enumerate(contacts, start=1):
        label = f"[CONTACT-{index}]"
        lines.append(_record_line(label, {
            "name": record.full_name,
            "title": record.title,
            "type": record.contact_type,
            "agency": record.agency_name,
            "vendor": record.vendor_name,
            "last_contacted_at": _iso(record.last_contacted_at),
            "notes": _text(record.notes, 700),
            "tags": record.tags,
        }))
        sources.append(GroundingSource(label, "contact", record.full_name))

    files = FileRecord.objects.filter(organization=organization).order_by("-updated_at")[:8]
    for index, record in enumerate(files, start=1):
        label = f"[FILE-{index}]"
        lines.append(_record_line(label, {
            "name": record.name,
            "file_type": record.file_type,
            "source": record.source,
            "source_url": record.source_url,
            "metadata": _text(json.dumps(record.metadata, default=str), 1200),
        }))
        sources.append(GroundingSource(label, "file", record.name, record.source_url))

    if not lines:
        lines.append("[NO-RECORDS] No ForgeGov workspace or public catalog records are currently available.")

    return "\n".join(lines), sources


def _extract_output_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text" and part.get("text"):
                chunks.append(str(part["text"]))
            elif part.get("type") == "refusal" and part.get("refusal"):
                chunks.append(str(part["refusal"]))
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def ask_openai(*, message: str, history: list[dict[str, str]], organization) -> dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        raise OpenAIIntegrationError(
            "OPENAI_API_KEY is not configured in the backend environment.",
            status_code=503,
        )

    grounding, sources = build_grounding_context(organization)
    web_context, web_sources = search_live_web(message)
    sources.extend(web_sources)
    safe_history = []
    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = _text(item.get("content"), 4000)
        if role in {"user", "assistant"} and content:
            safe_history.append({"role": role, "content": content})

    conversation = "\n".join(f"{item['role'].upper()}: {item['content']}" for item in safe_history)
    prompt = (
        "FORGEGOV GROUNDED RECORDS\n"
        f"{grounding}\n\n"
        "LIVE WEB SEARCH RESULTS\n"
        f"{web_context or '(live web search not configured)'}\n\n"
        "PRIOR CONVERSATION\n"
        f"{conversation or '(none)'}\n\n"
        "CURRENT USER REQUEST\n"
        f"{message.strip()}"
    )

    payload: dict[str, Any] = {
        "model": settings.OPENAI_MODEL,
        "instructions": (
            "You are ForgeGov AI, a government-contracting research and capture assistant. "
            "Use the provided ForgeGov records as the source of truth for record-specific facts. "
            "Cite supporting records inline using their exact bracket labels, such as [OPP-1] or [PIPE-2]. "
            "Never invent deadlines, solicitation numbers, award values, contacts, certifications, incumbents, or source content. "
            "When the records do not support a claim, say what is missing. "
            "You may provide clearly labeled general GovCon guidance, but do not present it as a workspace fact. "
            "Keep recommendations practical and distinguish facts from inferences."
        ),
        "input": prompt,
        "max_output_tokens": settings.OPENAI_MAX_OUTPUT_TOKENS,
        "store": False,
    }

    client_request_id = str(uuid4())
    try:
        response = requests.post(
            f"{settings.OPENAI_API_BASE_URL.rstrip('/')}/responses",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "X-Client-Request-Id": client_request_id,
            },
            json=payload,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise OpenAIIntegrationError(
            "OpenAI could not be reached from the ForgeGov backend. Check network access and try again.",
            status_code=502,
        ) from exc

    try:
        body = response.json()
    except ValueError:
        body = {}

    if not response.ok:
        error = body.get("error") if isinstance(body, dict) else None
        detail = _text(error.get("message") if isinstance(error, dict) else response.text, 500)
        if response.status_code in {401, 403}:
            message_text = "OpenAI rejected the API key or project permissions. Verify the server-side key and project access."
        elif response.status_code == 429:
            message_text = "OpenAI rate or billing limits were reached. Check API billing, project limits, and retry shortly."
        elif response.status_code == 404:
            message_text = f"The configured OpenAI model '{settings.OPENAI_MODEL}' is unavailable to this API project."
        else:
            message_text = f"OpenAI returned HTTP {response.status_code}."
        if detail:
            message_text = f"{message_text} {detail}"
        raise OpenAIIntegrationError(message_text, status_code=429 if response.status_code == 429 else 502)

    answer = _extract_output_text(body if isinstance(body, dict) else {})
    if not answer:
        raise OpenAIIntegrationError("OpenAI returned no usable text output.", status_code=502)

    return {
        "answer": answer,
        "model": body.get("model") or settings.OPENAI_MODEL,
        "response_id": body.get("id"),
        "request_id": response.headers.get("x-request-id") or client_request_id,
        "usage": body.get("usage") or {},
        "sources": [source.as_dict() for source in sources],
        "provider": "openai",
        "web_enabled": bool(getattr(settings, "SEARXNG_URL", "")),
    }


def search_live_web(query: str) -> tuple[str, list[GroundingSource]]:
    """Optional live search through a user-controlled SearXNG instance."""
    if not getattr(settings, "AI_WEB_SEARCH_ENABLED", True) or not getattr(settings, "SEARXNG_URL", ""):
        return "", []
    try:
        response = requests.get(settings.SEARXNG_URL.rstrip("/") + "/search", params={"q": query, "format": "json", "language": "en-US", "safesearch": 1}, timeout=18, headers={"User-Agent": "ForgeGov/2.0"})
        response.raise_for_status()
        rows = response.json().get("results", [])[:8]
    except (requests.RequestException, ValueError, AttributeError):
        return "", []
    lines=[]; sources=[]
    for index,row in enumerate(rows,1):
        label=f"[WEB-{index}]"; title=_text(row.get("title"),300); url=_text(row.get("url"),1000)
        lines.append(_record_line(label,{"title":title,"url":url,"snippet":_text(row.get("content"),900)}))
        sources.append(GroundingSource(label,"web",title,url))
    return "\n".join(lines), sources


def ask_ollama(*, message: str, history: list[dict[str, str]], organization) -> dict[str, Any]:
    grounding, sources = build_grounding_context(organization)
    web_context, web_sources = search_live_web(message)
    sources.extend(web_sources)
    safe_history=[{"role":i.get("role"),"content":_text(i.get("content"),4000)} for i in history[-12:] if isinstance(i,dict) and i.get("role") in {"user","assistant"}]
    system=("You are ForgeGov AI, a government-contracting research and capture assistant. Cite exact source labels. "
            "Separate verified facts, analysis, risks, and recommended next actions. Never invent records or live-web facts.")
    user = (
        "FORGEGOV RECORDS\n"
        f"{grounding}\n\n"
        "LIVE WEB RESULTS\n"
        f"{web_context or '(not configured)'}\n\n"
        "REQUEST\n"
        f"{message.strip()}"
    )
    try:
        response=requests.post(settings.OLLAMA_BASE_URL.rstrip("/")+"/api/chat",json={"model":settings.OLLAMA_MODEL,"stream":False,"messages":[{"role":"system","content":system},*safe_history,{"role":"user","content":user}],"options":{"temperature":0.2}},timeout=max(settings.OPENAI_TIMEOUT_SECONDS,90))
        response.raise_for_status(); body=response.json(); answer=_text((body.get("message") or {}).get("content"),20000)
    except (requests.RequestException,ValueError) as exc:
        raise OpenAIIntegrationError("The self-hosted Ollama model could not be reached. Confirm Ollama is running and the configured model is installed.",status_code=502) from exc
    if not answer: raise OpenAIIntegrationError("The self-hosted model returned no usable answer.",status_code=502)
    return {"answer":answer,"model":settings.OLLAMA_MODEL,"provider":"ollama","sources":[source.as_dict() for source in sources],"web_enabled":bool(settings.SEARXNG_URL)}


def ask_ai(*, message: str, history: list[dict[str, str]], organization) -> dict[str, Any]:
    provider=getattr(settings,"AI_PROVIDER","openai").lower()
    if provider == "ollama":
        return ask_ollama(message=message,history=history,organization=organization)
    # Include optional self-hosted web results in the hosted-provider prompt too.
    return ask_openai(message=message,history=history,organization=organization)
