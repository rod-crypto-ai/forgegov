from __future__ import annotations

import hashlib
import json
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Membership,
    OpportunityDocument,
    OpportunityWorkspace,
    PipelineItem,
    ProposalFinding,
    ProposalPlan,
    ProposalRequirement,
    ProposalReview,
    ProjectRoomTask,
)
from .proposal_workspace import build_proposal_workspace


def _snapshot(opportunity, documents) -> dict[str, Any]:
    doc_rows = [
        {
            "url": doc.source_url,
            "checksum": doc.checksum,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
        for doc in documents
    ]
    payload = {
        "source_modified_at": opportunity.source_modified_at.isoformat() if opportunity.source_modified_at else None,
        "response_deadline": opportunity.response_deadline.isoformat() if opportunity.response_deadline else None,
        "resource_links": opportunity.resource_links or [],
        "documents": doc_rows,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return {"fingerprint": hashlib.sha256(encoded).hexdigest(), **payload}


def _display_user(user) -> str:
    if not user:
        return ""
    return user.get_full_name() or user.username


def _member_options(organization) -> list[dict[str, Any]]:
    return [
        {
            "user_id": row.user_id,
            "name": _display_user(row.user),
            "role": row.role,
        }
        for row in Membership.objects.filter(organization=organization, active=True).select_related("user").order_by("user__username")
    ]


def ensure_proposal_execution(*, organization, opportunity, user=None) -> ProposalPlan:
    plan, _ = ProposalPlan.objects.get_or_create(
        organization=organization,
        opportunity=opportunity,
        defaults={"created_by": user},
    )
    documents = list(OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at"))
    current_snapshot = _snapshot(opportunity, documents)
    if not plan.amendment_baseline:
        plan.amendment_baseline = current_snapshot
        plan.amendment_checked_at = timezone.now()
        plan.save(update_fields=["amendment_baseline", "amendment_checked_at", "updated_at"])

    calculated = build_proposal_workspace(organization=organization, opportunity=opportunity)
    for order, row in enumerate(calculated.get("compliance_matrix") or []):
        key = str(row.get("id") or f"derived-{order+1}")[:160]
        requirement, created = ProposalRequirement.objects.get_or_create(
            plan=plan,
            key=key,
            defaults={
                "requirement": str(row.get("requirement") or "Untitled requirement"),
                "source": str(row.get("source") or ""),
                "source_kind": str(row.get("source_kind") or ""),
                "evidence": str(row.get("evidence") or ""),
                "status": ProposalRequirement.Status.NEEDS_REVIEW,
                "sort_order": order,
            },
        )
        if not created:
            changed = []
            for field, value in {
                "requirement": str(row.get("requirement") or requirement.requirement),
                "source": str(row.get("source") or requirement.source),
                "source_kind": str(row.get("source_kind") or requirement.source_kind),
                "evidence": str(row.get("evidence") or requirement.evidence),
                "sort_order": order,
            }.items():
                if getattr(requirement, field) != value:
                    setattr(requirement, field, value)
                    changed.append(field)
            if changed:
                requirement.save(update_fields=[*changed, "updated_at"])

    deadline = opportunity.response_deadline
    offsets = {
        ProposalReview.ReviewType.PINK: 21,
        ProposalReview.ReviewType.RED: 10,
        ProposalReview.ReviewType.GOLD: 4,
        ProposalReview.ReviewType.FINAL: 1,
    }
    for review_type, days in offsets.items():
        target = deadline - timezone.timedelta(days=days) if deadline else None
        review, created = ProposalReview.objects.get_or_create(
            plan=plan,
            review_type=review_type,
            defaults={"target_at": target},
        )
        if not created and review.status == ProposalReview.Status.PLANNED and target and review.target_at != target:
            review.target_at = target
            review.save(update_fields=["target_at", "updated_at"])
    return plan


def _amendment_status(plan: ProposalPlan, opportunity, documents) -> dict[str, Any]:
    current = _snapshot(opportunity, documents)
    baseline = plan.amendment_baseline or {}
    changed = bool(baseline and baseline.get("fingerprint") != current.get("fingerprint"))
    changes: list[str] = []
    if changed:
        if baseline.get("source_modified_at") != current.get("source_modified_at"):
            changes.append("Official source modified timestamp changed.")
        if baseline.get("response_deadline") != current.get("response_deadline"):
            changes.append("Response deadline changed.")
        if baseline.get("resource_links") != current.get("resource_links"):
            changes.append("Opportunity attachment/resource links changed.")
        old_docs = {(d.get("url"), d.get("checksum")) for d in baseline.get("documents") or []}
        new_docs = {(d.get("url"), d.get("checksum")) for d in current.get("documents") or []}
        if old_docs != new_docs:
            changes.append("Indexed solicitation document set or checksum changed.")
    return {
        "changed": changed,
        "changes": changes,
        "baseline": baseline,
        "current": current,
        "checked_at": plan.amendment_checked_at.isoformat() if plan.amendment_checked_at else None,
    }


def proposal_execution_payload(*, organization, opportunity, user=None) -> dict[str, Any]:
    plan = ensure_proposal_execution(organization=organization, opportunity=opportunity, user=user)
    documents = list(OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at"))
    requirements = list(plan.requirements.select_related("owner").all())
    reviews = list(plan.reviews.select_related("owner").all())
    findings = list(plan.findings.select_related("owner", "review", "requirement").all())
    amendment = _amendment_status(plan, opportunity, documents)

    closed_requirements = sum(1 for row in requirements if row.status in {ProposalRequirement.Status.COMPLIANT, ProposalRequirement.Status.NOT_APPLICABLE})
    open_findings = [row for row in findings if row.status == ProposalFinding.Status.OPEN]
    passed_reviews = sum(1 for row in reviews if row.status == ProposalReview.Status.PASSED)
    blocked_reviews = sum(1 for row in reviews if row.status == ProposalReview.Status.BLOCKED)
    critical_open = sum(1 for row in open_findings if row.severity == ProposalFinding.Severity.CRITICAL)
    submission_ready = bool(
        requirements
        and closed_requirements == len(requirements)
        and reviews
        and passed_reviews == len(reviews)
        and not open_findings
        and plan.final_submission_verified
        and not amendment["changed"]
    )
    if submission_ready and plan.status != ProposalPlan.Status.SUBMITTED:
        status_value = ProposalPlan.Status.SUBMISSION_READY
    elif blocked_reviews or critical_open:
        status_value = ProposalPlan.Status.REVIEW
    elif any(row.status == ProposalRequirement.Status.IN_PROGRESS for row in requirements):
        status_value = ProposalPlan.Status.IN_PROGRESS
    else:
        status_value = plan.status
    if plan.status != ProposalPlan.Status.SUBMITTED and plan.status != status_value:
        plan.status = status_value
        plan.save(update_fields=["status", "updated_at"])

    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).select_related("project_room").first()
    project_tasks = []
    if pipeline and pipeline.project_room_id:
        for task in ProjectRoomTask.objects.filter(project_room_id=pipeline.project_room_id).select_related("assigned_to").order_by("status", "due_date")[:100]:
            project_tasks.append({
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "assigned_to": _display_user(task.assigned_to),
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "source": "project_room",
            })

    readiness = round(
        (
            (closed_requirements / max(1, len(requirements))) * 50
            + (passed_reviews / max(1, len(reviews))) * 25
            + (0 if open_findings else 15)
            + (10 if plan.final_submission_verified else 0)
        )
    )
    if amendment["changed"]:
        readiness = min(readiness, 75)

    return {
        "plan": {
            "id": plan.id,
            "status": plan.status,
            "submission_method": plan.submission_method,
            "final_submission_verified": plan.final_submission_verified,
            "submission_ready": submission_ready,
            "readiness_score": readiness,
        },
        "requirements": [
            {
                "id": row.id,
                "key": row.key,
                "requirement": row.requirement,
                "source": row.source,
                "source_kind": row.source_kind,
                "evidence": row.evidence,
                "status": row.status,
                "owner_id": row.owner_id,
                "owner": _display_user(row.owner),
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "notes": row.notes,
                "open_findings": row.findings.filter(status=ProposalFinding.Status.OPEN).count(),
            }
            for row in requirements
        ],
        "reviews": [
            {
                "id": row.id,
                "review_type": row.review_type,
                "label": row.get_review_type_display(),
                "target_at": row.target_at.isoformat() if row.target_at else None,
                "status": row.status,
                "owner_id": row.owner_id,
                "owner": _display_user(row.owner),
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "summary": row.summary,
                "open_findings": row.findings.filter(status=ProposalFinding.Status.OPEN).count(),
            }
            for row in reviews
        ],
        "findings": [
            {
                "id": row.id,
                "review_id": row.review_id,
                "requirement_id": row.requirement_id,
                "severity": row.severity,
                "title": row.title,
                "detail": row.detail,
                "status": row.status,
                "owner_id": row.owner_id,
                "owner": _display_user(row.owner),
                "due_at": row.due_at.isoformat() if row.due_at else None,
            }
            for row in findings
        ],
        "members": _member_options(organization),
        "amendment_impact": amendment,
        "project_room_tasks": project_tasks,
        "counts": {
            "requirements_total": len(requirements),
            "requirements_closed": closed_requirements,
            "reviews_total": len(reviews),
            "reviews_passed": passed_reviews,
            "open_findings": len(open_findings),
            "critical_open_findings": critical_open,
        },
        "warning": "ForgeGov tracks proposal execution state but does not certify compliance. A responsible human must verify each requirement and the current official solicitation before submission.",
    }


def update_plan(plan: ProposalPlan, payload: dict[str, Any]) -> ProposalPlan:
    allowed_status = {value for value, _ in ProposalPlan.Status.choices}
    if "status" in payload and payload["status"] in allowed_status:
        plan.status = payload["status"]
    if "submission_method" in payload:
        plan.submission_method = str(payload.get("submission_method") or "")[:500]
    if "final_submission_verified" in payload:
        plan.final_submission_verified = bool(payload.get("final_submission_verified"))
    plan.save()
    return plan


def update_requirement(requirement: ProposalRequirement, payload: dict[str, Any], organization) -> ProposalRequirement:
    allowed_status = {value for value, _ in ProposalRequirement.Status.choices}
    if payload.get("status") in allowed_status:
        requirement.status = payload["status"]
    if "notes" in payload:
        requirement.notes = str(payload.get("notes") or "")
    if "due_at" in payload:
        requirement.due_at = payload.get("due_at") or None
    if "owner_id" in payload:
        user_id = payload.get("owner_id")
        valid = Membership.objects.filter(organization=organization, user_id=user_id, active=True).exists() if user_id else True
        if valid:
            requirement.owner_id = user_id or None
    requirement.save()
    return requirement


def update_review(review: ProposalReview, payload: dict[str, Any], organization) -> ProposalReview:
    allowed_status = {value for value, _ in ProposalReview.Status.choices}
    if payload.get("status") in allowed_status:
        review.status = payload["status"]
        if review.status == ProposalReview.Status.PASSED and not review.completed_at:
            review.completed_at = timezone.now()
        elif review.status != ProposalReview.Status.PASSED:
            review.completed_at = None
    if "summary" in payload:
        review.summary = str(payload.get("summary") or "")
    if "target_at" in payload:
        review.target_at = payload.get("target_at") or None
    if "owner_id" in payload:
        user_id = payload.get("owner_id")
        valid = Membership.objects.filter(organization=organization, user_id=user_id, active=True).exists() if user_id else True
        if valid:
            review.owner_id = user_id or None
    review.save()
    return review


def update_finding(finding: ProposalFinding, payload: dict[str, Any], organization) -> ProposalFinding:
    allowed_status = {value for value, _ in ProposalFinding.Status.choices}
    allowed_severity = {value for value, _ in ProposalFinding.Severity.choices}
    if payload.get("status") in allowed_status:
        finding.status = payload["status"]
    if payload.get("severity") in allowed_severity:
        finding.severity = payload["severity"]
    for field in ("title", "detail"):
        if field in payload:
            setattr(finding, field, str(payload.get(field) or ""))
    if "due_at" in payload:
        finding.due_at = payload.get("due_at") or None
    if "owner_id" in payload:
        user_id = payload.get("owner_id")
        valid = Membership.objects.filter(organization=organization, user_id=user_id, active=True).exists() if user_id else True
        if valid:
            finding.owner_id = user_id or None
    finding.save()
    return finding
