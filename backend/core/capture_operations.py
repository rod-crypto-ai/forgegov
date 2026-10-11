from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import (
    CaptureMilestone,
    CapturePlan,
    Membership,
    PipelineItem,
    Pursuit,
    PursuitChange,
    PursuitDecisionSnapshot,
    Task,
    WeeklyCaptureReview,
)
from .permissions import ReadOnlyOrContributor, active_membership


ACTIVE_STAGES = {
    Pursuit.Stage.TRIAGE,
    Pursuit.Stage.QUALIFY,
    Pursuit.Stage.BID_DECISION,
    Pursuit.Stage.CAPTURE,
    Pursuit.Stage.PROPOSAL,
    Pursuit.Stage.SUBMITTED,
}
CLOSED_STAGES = {Pursuit.Stage.AWARDED, Pursuit.Stage.LOST, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED}
ALLOWED_TRANSITIONS = {
    Pursuit.Stage.TRIAGE: {Pursuit.Stage.QUALIFY, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.QUALIFY: {Pursuit.Stage.BID_DECISION, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.BID_DECISION: {Pursuit.Stage.CAPTURE, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.CAPTURE: {Pursuit.Stage.PROPOSAL, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.PROPOSAL: {Pursuit.Stage.SUBMITTED, Pursuit.Stage.NO_BID, Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.SUBMITTED: {Pursuit.Stage.AWARDED, Pursuit.Stage.LOST},
    Pursuit.Stage.AWARDED: {Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.LOST: {Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.NO_BID: {Pursuit.Stage.ARCHIVED},
    Pursuit.Stage.ARCHIVED: set(),
}

MILESTONE_TEMPLATES = {
    "standard": [
        ("qualification", "Confirm customer need and acquisition fit"),
        ("decision", "Complete evidence-backed bid / no-bid review"),
        ("capture", "Approve win strategy and accountable owner"),
        ("teaming", "Resolve teaming and capability gaps"),
        ("proposal", "Complete proposal readiness review"),
        ("submission", "Approve submission package and delivery plan"),
    ],
    "accelerated": [
        ("qualification", "Confirm minimum qualification evidence"),
        ("decision", "Record expedited bid / no-bid decision"),
        ("capture", "Confirm owner, next action, and win strategy"),
        ("submission", "Complete final compliance and submission check"),
    ],
}


def _organization(request):
    membership = active_membership(request.user)
    return membership.organization if membership else None


def _week_start(day):
    return day - timedelta(days=day.weekday())


def _milestone_payload(row):
    return {
        "id": row.id,
        "title": row.title,
        "category": row.category,
        "position": row.position,
        "owner_id": row.owner_id,
        "owner_name": (row.owner.get_full_name() or row.owner.email) if row.owner else "",
        "due_at": row.due_at,
        "required": row.required,
        "completed_at": row.completed_at,
        "depends_on_id": row.depends_on_id,
        "blocked": bool(row.depends_on_id and not row.depends_on.completed_at),
    }


def _plan_payload(plan):
    milestones = list(plan.milestones.select_related("owner", "depends_on"))
    completed = sum(1 for row in milestones if row.completed_at)
    return {
        "id": plan.id,
        "status": plan.status,
        "template_key": plan.template_key,
        "objective": plan.objective,
        "customer_need": plan.customer_need,
        "win_strategy": plan.win_strategy,
        "key_risks": plan.key_risks,
        "progress_percent": round(completed / len(milestones) * 100) if milestones else 0,
        "milestones": [_milestone_payload(row) for row in milestones],
    }


def _gate_findings(pursuit, target_stage):
    findings = []
    if target_stage in {Pursuit.Stage.BID_DECISION, Pursuit.Stage.CAPTURE, Pursuit.Stage.PROPOSAL, Pursuit.Stage.SUBMITTED}:
        if not pursuit.owner_id:
            findings.append("Assign an accountable pursuit owner.")
        if not pursuit.next_action.strip():
            findings.append("Record the next action.")
    if target_stage in {Pursuit.Stage.CAPTURE, Pursuit.Stage.PROPOSAL, Pursuit.Stage.SUBMITTED}:
        decision = PursuitDecisionSnapshot.objects.filter(
            organization=pursuit.organization,
            opportunity=pursuit.opportunity,
        ).first() if pursuit.opportunity_id else None
        if not decision:
            findings.append("Complete and record the bid / no-bid review.")
        elif str(decision.recommendation).lower().replace("-", "_") in {"no_bid", "hold"}:
            findings.append(f"The latest recorded decision is {decision.recommendation}.")
    if target_stage in {Pursuit.Stage.PROPOSAL, Pursuit.Stage.SUBMITTED}:
        plan = CapturePlan.objects.filter(organization=pursuit.organization, pursuit=pursuit).first()
        if not plan:
            findings.append("Create a capture plan and apply a milestone template.")
        else:
            open_required = plan.milestones.filter(required=True, completed_at__isnull=True).count()
            if open_required:
                findings.append(f"Complete {open_required} required capture milestone(s).")
    return findings


def _operations_payload(organization):
    now = timezone.now()
    today = now.date()
    horizon = now + timedelta(days=14)
    pursuits = list(
        Pursuit.objects.filter(organization=organization)
        .select_related("owner", "opportunity")
        .prefetch_related("capture_plan__milestones__owner", "capture_plan__milestones__depends_on")
        .order_by("due_date", "-updated_at")
    )
    active = [row for row in pursuits if row.stage in ACTIVE_STAGES]
    workload = defaultdict(lambda: {"owner_id": None, "owner_name": "Unassigned", "pursuits": 0, "open_tasks": 0, "overdue_tasks": 0})
    for row in active:
        key = row.owner_id or 0
        workload[key]["owner_id"] = row.owner_id
        workload[key]["owner_name"] = (row.owner.get_full_name() or row.owner.email) if row.owner else "Unassigned"
        workload[key]["pursuits"] += 1
    for task in Task.objects.filter(organization=organization, completed=False).select_related("assigned_to"):
        key = task.assigned_to_id or 0
        workload[key]["owner_id"] = task.assigned_to_id
        workload[key]["owner_name"] = (task.assigned_to.get_full_name() or task.assigned_to.email) if task.assigned_to else "Unassigned"
        workload[key]["open_tasks"] += 1
        if task.due_at and task.due_at < now:
            workload[key]["overdue_tasks"] += 1

    rows = []
    agency_totals = defaultdict(Decimal)
    total_value = Decimal("0")
    weighted_value = Decimal("0")
    review_queue = []
    for row in active:
        value = row.estimated_value or Decimal("0")
        weighted = value * Decimal(row.probability_of_win or 0) / Decimal("100")
        total_value += value
        weighted_value += weighted
        agency = ((row.opportunity.agency if row.opportunity else "") or "Agency unavailable").strip()
        agency_totals[agency] += value
        age_days = max(0, (today - row.created_at.date()).days)
        stale_days = max(0, (today - row.updated_at.date()).days)
        plan = getattr(row, "capture_plan", None)
        findings = _gate_findings(row, row.stage)
        urgency = 0
        signals = []
        if row.due_date and row.due_date < now:
            urgency += 100
            signals.append("Overdue pursuit deadline")
        elif row.due_date and row.due_date <= horizon:
            urgency += 60
            signals.append("Due within 14 days")
        if stale_days >= 14:
            urgency += 40
            signals.append(f"No update for {stale_days} days")
        if not row.owner_id:
            urgency += 35
            signals.append("Owner unassigned")
        if not row.next_action.strip():
            urgency += 25
            signals.append("Next action missing")
        payload = {
            "id": row.id,
            "title": row.title,
            "stage": row.stage,
            "owner_id": row.owner_id,
            "owner_name": (row.owner.get_full_name() or row.owner.email) if row.owner else "",
            "estimated_value": value,
            "probability_of_win": row.probability_of_win,
            "weighted_value": weighted,
            "due_date": row.due_date,
            "next_action": row.next_action,
            "age_days": age_days,
            "stale_days": stale_days,
            "agency": agency,
            "plan": _plan_payload(plan) if plan else None,
            "gate_findings": findings,
            "allowed_transitions": sorted(ALLOWED_TRANSITIONS.get(row.stage, set())),
        }
        rows.append(payload)
        if signals:
            review_queue.append({"pursuit_id": row.id, "title": row.title, "urgency": urgency, "signals": signals})

    review_queue.sort(key=lambda item: (-item["urgency"], item["title"]))
    concentration = [
        {"agency": agency, "value": value, "share_percent": round(float(value / total_value * 100), 1) if total_value else 0}
        for agency, value in sorted(agency_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    monday = _week_start(today)
    review = WeeklyCaptureReview.objects.filter(organization=organization, week_start=monday).first()
    history = PursuitChange.objects.filter(organization=organization).select_related("pursuit", "changed_by")[:20]
    pipeline_opportunity_ids = set(PipelineItem.objects.filter(organization=organization).values_list("opportunity_id", flat=True))
    pursuit_opportunity_ids = {row.opportunity_id for row in active if row.opportunity_id}
    return {
        "definitions": {
            "active_pursuit": "Triage through Submitted; excludes Awarded, Lost, No-Bid, and Archived.",
            "pipeline_value": "Sum of active pursuit estimated values.",
            "weighted_pipeline": "Active pursuit estimated value multiplied by entered probability of win.",
            "stale": "No pursuit update for 14 or more days.",
        },
        "summary": {
            "active_pursuits": len(active),
            "pipeline_value": total_value,
            "weighted_pipeline": weighted_value,
            "overdue": sum(1 for row in active if row.due_date and row.due_date < now),
            "due_within_14_days": sum(1 for row in active if row.due_date and now <= row.due_date <= horizon),
            "stale": sum(1 for row in active if (today - row.updated_at.date()).days >= 14),
            "unassigned": sum(1 for row in active if not row.owner_id),
            "unlinked_pipeline_items": len(pipeline_opportunity_ids - pursuit_opportunity_ids),
        },
        "pursuits": rows,
        "review_queue": review_queue[:20],
        "workload": sorted(workload.values(), key=lambda item: (-item["overdue_tasks"], -item["open_tasks"], -item["pursuits"], item["owner_name"])),
        "agency_concentration": concentration[:10],
        "weekly_review": {
            "id": review.id if review else None,
            "week_start": monday,
            "status": review.status if review else WeeklyCaptureReview.Status.DRAFT,
            "notes": review.notes if review else "",
            "decisions": review.decisions if review else [],
        },
        "recent_changes": [{
            "id": change.id,
            "pursuit_id": change.pursuit_id,
            "title": change.pursuit.title,
            "previous_stage": change.previous_stage,
            "new_stage": change.new_stage,
            "previous_probability": change.previous_probability,
            "new_probability": change.new_probability,
            "reason": change.reason,
            "source": change.source,
            "changed_by": (change.changed_by.get_full_name() or change.changed_by.email) if change.changed_by else "System",
            "created_at": change.created_at,
        } for change in history],
        "templates": [{"key": key, "name": key.replace("_", " ").title(), "milestone_count": len(items)} for key, items in MILESTONE_TEMPLATES.items()],
    }


@api_view(["GET", "POST"])
@permission_classes([ReadOnlyOrContributor])
def capture_operations_view(request):
    organization = _organization(request)
    if request.method == "GET":
        return Response(_operations_payload(organization))

    action = str(request.data.get("action") or "").strip()
    if action == "apply_template":
        pursuit = Pursuit.objects.filter(organization=organization, pk=request.data.get("pursuit_id")).first()
        template_key = str(request.data.get("template_key") or "standard")
        if not pursuit or template_key not in MILESTONE_TEMPLATES:
            return Response({"detail": "Pursuit or milestone template not found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            plan, _ = CapturePlan.objects.get_or_create(
                organization=organization,
                pursuit=pursuit,
                defaults={"template_key": template_key, "status": CapturePlan.Status.ACTIVE, "created_by": request.user},
            )
            plan.template_key = template_key
            plan.status = CapturePlan.Status.ACTIVE
            plan.save(update_fields=["template_key", "status", "updated_at"])
            previous = None
            for position, (category, title) in enumerate(MILESTONE_TEMPLATES[template_key], start=1):
                milestone, _ = CaptureMilestone.objects.get_or_create(
                    organization=organization,
                    plan=plan,
                    title=title,
                    defaults={"category": category, "position": position, "owner": pursuit.owner, "depends_on": previous},
                )
                previous = milestone
        return Response(_operations_payload(organization), status=status.HTTP_201_CREATED)

    if action == "complete_milestone":
        milestone = CaptureMilestone.objects.select_related("depends_on").filter(organization=organization, pk=request.data.get("milestone_id")).first()
        if not milestone:
            return Response({"detail": "Milestone not found."}, status=status.HTTP_404_NOT_FOUND)
        complete = bool(request.data.get("complete", True))
        if complete and milestone.depends_on_id and not milestone.depends_on.completed_at:
            return Response({"detail": "Complete the prerequisite milestone first."}, status=status.HTTP_409_CONFLICT)
        milestone.completed_at = timezone.now() if complete else None
        milestone.save(update_fields=["completed_at", "updated_at"])
        return Response(_operations_payload(organization))

    if action == "update_plan":
        plan = CapturePlan.objects.filter(organization=organization, pk=request.data.get("plan_id")).first()
        if not plan:
            return Response({"detail": "Capture plan not found."}, status=status.HTTP_404_NOT_FOUND)
        fields = []
        for field in ("objective", "customer_need", "win_strategy"):
            if field in request.data:
                setattr(plan, field, str(request.data.get(field) or ""))
                fields.append(field)
        if "key_risks" in request.data:
            risks = request.data.get("key_risks")
            if not isinstance(risks, list):
                return Response({"detail": "key_risks must be a list."}, status=status.HTTP_400_BAD_REQUEST)
            plan.key_risks = [str(item).strip() for item in risks if str(item).strip()][:20]
            fields.append("key_risks")
        if fields:
            plan.save(update_fields=[*fields, "updated_at"])
        return Response(_operations_payload(organization))

    if action == "transition":
        pursuit = Pursuit.objects.filter(organization=organization, pk=request.data.get("pursuit_id")).first()
        target = str(request.data.get("stage") or "")
        if not pursuit or target not in dict(Pursuit.Stage.choices):
            return Response({"detail": "Pursuit or target stage not found."}, status=status.HTTP_404_NOT_FOUND)
        if target not in ALLOWED_TRANSITIONS.get(pursuit.stage, set()):
            return Response({"detail": f"Transition from {pursuit.stage} to {target} is not permitted."}, status=status.HTTP_409_CONFLICT)
        findings = _gate_findings(pursuit, target)
        override_reason = str(request.data.get("override_reason") or "").strip()
        if findings and not override_reason:
            return Response({"detail": "Stage gate requirements are incomplete.", "findings": findings}, status=status.HTTP_409_CONFLICT)
        previous = pursuit.stage
        pursuit.stage = target
        pursuit.save(update_fields=["stage", "updated_at"])
        PursuitChange.objects.create(
            organization=organization,
            pursuit=pursuit,
            changed_by=request.user,
            previous_stage=previous,
            new_stage=target,
            previous_probability=pursuit.probability_of_win,
            new_probability=pursuit.probability_of_win,
            reason=override_reason,
            source="stage_gate",
        )
        return Response(_operations_payload(organization))

    if action == "record_weekly_review":
        monday = _week_start(timezone.localdate())
        review, _ = WeeklyCaptureReview.objects.get_or_create(
            organization=organization,
            week_start=monday,
            defaults={"created_by": request.user},
        )
        review.notes = str(request.data.get("notes") or "")
        review.decisions = request.data.get("decisions") if isinstance(request.data.get("decisions"), list) else review.decisions
        review.status = WeeklyCaptureReview.Status.COMPLETE if request.data.get("complete") else WeeklyCaptureReview.Status.DRAFT
        review.save(update_fields=["notes", "decisions", "status", "updated_at"])
        return Response(_operations_payload(organization))

    return Response({"detail": "Unsupported capture operation."}, status=status.HTTP_400_BAD_REQUEST)
