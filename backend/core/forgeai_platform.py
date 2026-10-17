from __future__ import annotations

import hashlib
from collections import Counter
from datetime import timedelta
from typing import Any

from django.db import IntegrityError
from django.utils import timezone

from .models import (
    Award,
    FileRecord,
    ForgeAIResearchRun,
    Opportunity,
    OrganizationProfile,
    ProjectRoom,
    ProposalPlan,
    Pursuit,
)

WORKFLOWS = {value for value, _ in ForgeAIResearchRun.Workflow.choices}
STALE_RUN_AFTER = timedelta(minutes=5)


class DuplicateResearchRun(RuntimeError):
    pass


def request_fingerprint(*, organization_id: int, user_id: int, workflow: str, message: str) -> str:
    normalized = " ".join(str(message or "").split()).casefold()
    material = f"{organization_id}:{user_id}:{workflow}:{normalized}".encode()
    return hashlib.sha256(material).hexdigest()


def start_research_run(*, organization, user, workflow: str, message: str) -> ForgeAIResearchRun:
    workflow = workflow if workflow in WORKFLOWS else ForgeAIResearchRun.Workflow.RESEARCH
    fingerprint = request_fingerprint(
        organization_id=organization.id,
        user_id=user.id,
        workflow=workflow,
        message=message,
    )
    stale_before = timezone.now() - STALE_RUN_AFTER
    ForgeAIResearchRun.objects.filter(
        organization=organization,
        created_by=user,
        request_fingerprint=fingerprint,
        status=ForgeAIResearchRun.Status.RUNNING,
        created_at__lt=stale_before,
    ).update(
        status=ForgeAIResearchRun.Status.FAILED,
        error_code="stale_run_recovered",
        completed_at=timezone.now(),
    )
    try:
        return ForgeAIResearchRun.objects.create(
            organization=organization,
            created_by=user,
            workflow=workflow,
            request_fingerprint=fingerprint,
        )
    except IntegrityError as exc:
        raise DuplicateResearchRun("An identical ForgeAI request is already running.") from exc


def evidence_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = Counter(str(row.get("classification") or "unclassified") for row in sources)
    source_types = Counter(str(row.get("type") or "unknown") for row in sources)
    return {
        "source_count": len(sources),
        "classifications": dict(sorted(classifications.items())),
        "source_types": dict(sorted(source_types.items())),
        "has_official_or_stored_evidence": bool(classifications.get("official") or classifications.get("stored_public")),
        "has_workspace_evidence": bool(classifications.get("workspace")),
        "has_live_web_evidence": bool(classifications.get("live_web")),
        "coverage_note": "Source counts show what was supplied to the model; they do not independently verify completeness or correctness.",
    }


def complete_research_run(run: ForgeAIResearchRun, result: dict[str, Any], *, conversation=None, financial_context_permitted: bool = False) -> dict[str, Any]:
    now = timezone.now()
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    summary = evidence_summary(sources)
    run.conversation = conversation
    run.status = ForgeAIResearchRun.Status.SUCCEEDED
    run.provider = str(result.get("provider") or "")[:80]
    run.model = str(result.get("model") or "")[:120]
    run.provider_response_id = str(result.get("response_id") or "")[:255]
    run.provider_request_id = str(result.get("request_id") or "")[:255]
    run.source_manifest = sources
    run.evidence_summary = summary
    run.token_usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    run.used_live_web = bool(result.get("web_enabled"))
    run.used_workspace_context = True
    run.financial_context_permitted = financial_context_permitted
    run.completed_at = now
    run.duration_ms = max(0, round((now - run.created_at).total_seconds() * 1000))
    run.save(update_fields=[
        "conversation", "status", "provider", "model", "provider_response_id", "provider_request_id",
        "source_manifest", "evidence_summary", "token_usage", "used_live_web", "used_workspace_context",
        "financial_context_permitted", "completed_at", "duration_ms", "updated_at",
    ])
    return summary


def fail_research_run(run: ForgeAIResearchRun | None, *, error_code: str) -> None:
    if not run:
        return
    now = timezone.now()
    run.status = ForgeAIResearchRun.Status.FAILED
    run.error_code = str(error_code or "provider_error")[:80]
    run.completed_at = now
    run.duration_ms = max(0, round((now - run.created_at).total_seconds() * 1000))
    run.save(update_fields=["status", "error_code", "completed_at", "duration_ms", "updated_at"])


def platform_payload(organization) -> dict[str, Any]:
    profile = OrganizationProfile.objects.filter(organization=organization).first()
    recent = ForgeAIResearchRun.objects.filter(organization=organization).select_related("created_by", "conversation")[:20]
    return {
        "release": "3.2.6",
        "workflows": [
            {"key": value, "label": label}
            for value, label in ForgeAIResearchRun.Workflow.choices
        ],
        "source_inventory": {
            "active_opportunities": Opportunity.objects.filter(active=True).count(),
            "stored_awards": Award.objects.count(),
            "workspace_pursuits": Pursuit.objects.filter(organization=organization).count(),
            "workspace_files": FileRecord.objects.filter(organization=organization).count(),
            "project_rooms": ProjectRoom.objects.filter(owner_organization=organization, deleted_at__isnull=True).count(),
            "proposal_plans": ProposalPlan.objects.filter(organization=organization).count(),
            "company_profile": "available" if profile else "not_configured",
        },
        "governance": {
            "organization_scoped": True,
            "financial_role_filtered": True,
            "source_provenance_recorded": True,
            "duplicate_running_requests_blocked": True,
            "provider_storage_disabled": True,
            "autonomous_record_changes": False,
            "human_review_required": True,
        },
        "recent_runs": [
            {
                "id": row.id,
                "conversation_id": row.conversation_id,
                "workflow": row.workflow,
                "status": row.status,
                "provider": row.provider,
                "model": row.model,
                "source_count": int((row.evidence_summary or {}).get("source_count") or 0),
                "used_live_web": row.used_live_web,
                "created_by": (row.created_by.get_full_name() or row.created_by.email or row.created_by.username) if row.created_by else "Former user",
                "created_at": row.created_at,
                "duration_ms": row.duration_ms,
            }
            for row in recent
        ],
    }
