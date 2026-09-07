from __future__ import annotations

import difflib
import hashlib
import json
from typing import Any

from django.db import transaction
from django.utils import timezone

from .ai import ask_ai
from .models import (
    OpportunityDocumentChunk,
    ProposalFinding,
    ProposalFindingComment,
    ProposalFindingEvidence,
    ProposalReviewRun,
    ProposalSection,
    ProposalSectionRevision,
)
from .proposal_automation import ensure_proposal_production

CRITERIA = (
    "requirement_coverage",
    "responsiveness",
    "evidence_strength",
    "specificity",
    "risk",
    "win_theme_alignment",
    "internal_consistency",
)


def _snapshots(plan) -> tuple[dict[str, Any], dict[str, Any], str]:
    opportunity = plan.opportunity
    chunks = list(
        OpportunityDocumentChunk.objects.filter(
            document__organization=plan.organization,
            document__opportunity=opportunity,
            document__status="ready",
        )
        .select_related("document")
        .order_by("document_id", "ordinal")
    )
    solicitation = {
        "opportunity": {
            "source_id": opportunity.source_id,
            "title": opportunity.title,
            "solicitation_number": opportunity.solicitation_number,
            "deadline": opportunity.response_deadline.isoformat()
            if opportunity.response_deadline
            else None,
        },
        "chunks": [
            {
                "id": c.id,
                "document_id": c.document_id,
                "file": c.document.file_name,
                "page": c.page_number,
                "section": c.section,
                "text": c.text[:3000],
            }
            for c in chunks[:120]
        ],
    }
    sections = list(
        ProposalSection.objects.filter(volume__plan=plan)
        .select_related("volume")
        .prefetch_related("requirement_links__requirement", "revisions")
        .order_by("volume__sort_order", "sort_order")
    )
    proposal = {
        "sections": [
            {
                "id": s.id,
                "volume": s.volume.title,
                "title": s.title,
                "type": s.section_type,
                "status": s.status,
                "content": s.content,
                "revision": (
                    s.revisions.first().revision if s.revisions.first() else 0
                ),
                "requirements": [
                    {
                        "id": x.requirement_id,
                        "key": x.requirement.key,
                        "text": x.requirement.requirement,
                        "source": x.requirement.source,
                    }
                    for x in s.requirement_links.all()
                ],
            }
            for s in sections
        ]
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {"solicitation": solicitation, "proposal": proposal},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    return solicitation, proposal, fingerprint


def create_review_run(
    *, organization, opportunity, user, review_type: str
) -> tuple[ProposalReviewRun, bool]:
    valid = {value for value, _ in ProposalReviewRun.ReviewType.choices}
    if review_type not in valid:
        raise ValueError("Invalid proposal review type.")
    plan = ensure_proposal_production(
        organization=organization, opportunity=opportunity, user=user
    )
    solicitation, proposal, fingerprint = _snapshots(plan)
    existing = ProposalReviewRun.objects.filter(
        plan=plan,
        review_type=review_type,
        input_fingerprint=fingerprint,
        status__in=["queued", "running"],
    ).first()
    if existing:
        return existing, False
    linked_review = (
        plan.reviews.filter(review_type=review_type).first()
        if review_type in {"pink", "red", "gold", "final"}
        else None
    )
    return ProposalReviewRun.objects.create(
        plan=plan,
        review=linked_review,
        review_type=review_type,
        input_fingerprint=fingerprint,
        solicitation_snapshot=solicitation,
        proposal_snapshot=proposal,
        initiated_by=user,
    ), True


def _json_answer(answer: str) -> dict[str, Any]:
    text = str(answer or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "ForgeAI review did not return valid structured JSON."
        ) from exc
    if not isinstance(value, dict):
        raise TypeError("ForgeAI review returned an invalid result shape.")
    return value


def _bounded_score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _review_input(run: ProposalReviewRun) -> dict[str, Any]:
    """Balance the model context between solicitation evidence and every proposal section."""
    source_chunks = run.solicitation_snapshot.get("chunks") or []
    proposal_sections = run.proposal_snapshot.get("sections") or []
    chunk_limit = max(400, min(1400, 36000 // max(1, len(source_chunks))))
    section_limit = max(800, min(6000, 42000 // max(1, len(proposal_sections))))
    solicitation = {
        "opportunity": run.solicitation_snapshot.get("opportunity") or {},
        "chunks": [
            {**row, "text": str(row.get("text") or "")[:chunk_limit]}
            for row in source_chunks
        ],
    }
    proposal = {
        "sections": [
            {**row, "content": str(row.get("content") or "")[:section_limit]}
            for row in proposal_sections
        ],
    }
    return {"solicitation": solicitation, "proposal": proposal}


@transaction.atomic
def execute_review_run(run: ProposalReviewRun) -> ProposalReviewRun:
    run.status = ProposalReviewRun.Status.RUNNING
    run.started_at = timezone.now()
    run.error = ""
    run.save(update_fields=["status", "started_at", "error", "updated_at"])
    prompt = (
        "FORGEGOV PROPOSAL REVIEW. Return JSON only with keys summary, scorecard, findings. "
        "scorecard must contain criterion, score (0-100), explanation, confidence (0-100). "
        "Use only these criteria: "
        + ", ".join(CRITERIA)
        + ". Findings must contain severity, title, detail, recommendation, confidence, requirement_id, section_id, citations. "
        "Each citation must contain document_chunk_id, quotation, locator. Classify gaps as unanswered, partial, unsupported, contradicted, or human_validation. "
        "Never invent a solicitation requirement, company proof point, score, or citation. A missing evidentiary basis must lower confidence and create a human_validation finding. "
        "Cross-check numbers, schedules, staffing, experience, certifications, technical claims, terminology, win themes, and requirements across all sections. "
        f"Review mode: {run.review_type}. INPUT: {json.dumps(_review_input(run), default=str)}"
    )
    try:
        result = ask_ai(
            message=prompt,
            history=[],
            organization=run.plan.organization,
            user=run.initiated_by,
        )
        parsed = _json_answer(result.get("answer", ""))
        scorecard = [
            {
                **row,
                "score": _bounded_score(row.get("score")),
                "confidence": _bounded_score(row.get("confidence")),
            }
            for row in (parsed.get("scorecard") or [])
            if isinstance(row, dict) and row.get("criterion") in CRITERIA
        ]
        run.scorecard = scorecard
        run.summary = str(parsed.get("summary") or "")[:20000]
        run.provider = str(result.get("provider") or "")[:80]
        run.model = str(result.get("model") or "")[:120]
        for row in parsed.get("findings") or []:
            if not isinstance(row, dict) or not str(row.get("title") or "").strip():
                continue
            section = (
                run.plan.volumes.filter(sections__id=row.get("section_id"))
                .values_list("sections__id", flat=True)
                .first()
            )
            requirement = run.plan.requirements.filter(
                id=row.get("requirement_id")
            ).first()
            severity = str(row.get("severity") or "medium").lower()
            if severity not in {value for value, _ in ProposalFinding.Severity.choices}:
                severity = "medium"
            finding = ProposalFinding.objects.create(
                plan=run.plan,
                review=run.review,
                review_run=run,
                requirement=requirement,
                section_id=section,
                severity=severity,
                title=str(row.get("title"))[:500],
                detail=str(row.get("detail") or ""),
                recommendation=str(row.get("recommendation") or ""),
                confidence=_bounded_score(row.get("confidence")),
                created_by=run.initiated_by,
            )
            for citation in row.get("citations") or []:
                if not isinstance(citation, dict):
                    continue
                chunk = OpportunityDocumentChunk.objects.filter(
                    id=citation.get("document_chunk_id"),
                    document__organization=run.plan.organization,
                    document__opportunity=run.plan.opportunity,
                ).first()
                ProposalFindingEvidence.objects.create(
                    finding=finding,
                    review_run=run,
                    requirement=requirement,
                    section_id=section,
                    document_chunk=chunk,
                    source_label=chunk.document.file_name
                    if chunk
                    else "Human validation required",
                    locator=str(citation.get("locator") or "")[:500],
                    quotation=str(citation.get("quotation") or "")[:4000],
                )
        run.status = ProposalReviewRun.Status.COMPLETED
        run.completed_at = timezone.now()
        run.save()
    except Exception as exc:  # noqa: BLE001 -- task failures must persist a failed run instead of escaping.
        run.status = ProposalReviewRun.Status.FAILED
        run.error = str(exc)[:4000]
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at", "updated_at"])
    return run


def compare_revisions(
    *,
    section: ProposalSection,
    older: ProposalSectionRevision,
    newer: ProposalSectionRevision,
) -> dict[str, Any]:
    if older.section_id != section.id or newer.section_id != section.id:
        raise ValueError(
            "Both revisions must belong to the requested proposal section."
        )
    old_lines, new_lines = older.content.splitlines(), newer.content.splitlines()
    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"revision-{older.revision}",
            tofile=f"revision-{newer.revision}",
            lineterm="",
        )
    )
    return {
        "section_id": section.id,
        "older": older.revision,
        "newer": newer.revision,
        "diff": diff,
        "changed": older.content != newer.content,
    }


def add_finding_comment(
    *, finding: ProposalFinding, user, body: str, resolution_event: bool = False
) -> ProposalFindingComment:
    clean = str(body or "").strip()
    if not clean:
        raise ValueError("Comment text is required.")
    return ProposalFindingComment.objects.create(
        finding=finding, author=user, body=clean, resolution_event=resolution_event
    )


def review_center_payload(
    *, plan, can_financial: bool, can_approve: bool
) -> dict[str, Any]:
    runs = []
    for run in plan.review_runs.select_related("initiated_by").all()[:50]:
        runs.append(
            {
                "id": run.id,
                "review_type": run.review_type,
                "status": run.status,
                "summary": run.summary,
                "scorecard": run.scorecard,
                "provider": run.provider,
                "model": run.model,
                "error": run.error,
                "input_fingerprint": run.input_fingerprint,
                "initiated_by": run.initiated_by.get_full_name()
                or run.initiated_by.username
                if run.initiated_by
                else "",
                "created_at": run.created_at.isoformat(),
                "completed_at": run.completed_at.isoformat()
                if run.completed_at
                else None,
            }
        )
    findings = []
    queryset = plan.findings.select_related(
        "owner", "resolved_by", "section", "requirement", "review"
    ).prefetch_related("evidence_items", "comments__author")
    for row in queryset:
        if (
            row.section
            and row.section.section_type == ProposalSection.SectionType.PRICING
            and not can_financial
        ):
            continue
        findings.append(
            {
                "id": row.id,
                "review_id": row.review_id,
                "review_run_id": row.review_run_id,
                "requirement_id": row.requirement_id,
                "section_id": row.section_id,
                "section": row.section.title if row.section else "",
                "severity": row.severity,
                "title": row.title,
                "detail": row.detail,
                "recommendation": row.recommendation,
                "confidence": row.confidence,
                "status": row.status,
                "owner_id": row.owner_id,
                "owner": row.owner.get_full_name() or row.owner.username
                if row.owner
                else "",
                "resolution_response": row.resolution_response,
                "resolved_by": row.resolved_by.get_full_name()
                or row.resolved_by.username
                if row.resolved_by
                else "",
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
                "evidence": [
                    {
                        "id": e.id,
                        "source_label": e.source_label,
                        "locator": e.locator,
                        "quotation": e.quotation,
                        "document_chunk_id": e.document_chunk_id,
                    }
                    for e in row.evidence_items.all()
                ],
                "comments": [
                    {
                        "id": c.id,
                        "body": c.body,
                        "author": c.author.get_full_name() or c.author.username
                        if c.author
                        else "",
                        "resolution_event": c.resolution_event,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in row.comments.all()
                ],
            }
        )
    sections = []
    for section in (
        ProposalSection.objects.filter(volume__plan=plan)
        .select_related("volume")
        .prefetch_related("revisions")
    ):
        if (
            section.section_type == ProposalSection.SectionType.PRICING
            and not can_financial
        ):
            continue
        sections.append(
            {
                "id": section.id,
                "title": section.title,
                "volume": section.volume.title,
                "status": section.status,
                "revision_count": section.revisions.count(),
                "revisions": [
                    {
                        "id": r.id,
                        "revision": r.revision,
                        "created_at": r.created_at.isoformat(),
                        "change_summary": r.change_summary,
                    }
                    for r in section.revisions.all()[:25]
                ],
            }
        )
    return {
        "runs": runs,
        "findings": findings,
        "sections": sections,
        "review_types": [
            {"value": value, "label": label}
            for value, label in ProposalReviewRun.ReviewType.choices
        ],
        "permissions": {"can_financial": can_financial, "can_approve": can_approve},
        "warning": "ForgeAI review is decision support, not a certification. An authorized human must validate requirements, evidence, findings, and the official solicitation.",
    }
