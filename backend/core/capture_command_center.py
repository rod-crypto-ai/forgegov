from __future__ import annotations

from typing import Any

from django.utils import timezone

from .capture_intelligence import build_capture_assessment
from .models import OpportunityAnalysis, PipelineItem, ProjectRoomActivity, ProjectRoomNote, ProjectRoomTask, Task
from .win_strategy import build_win_strategy


def _iso(value):
    return value.isoformat() if value else None


def _priority_rank(value: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(value or "medium"), 2)


def _project_room_payload(pipeline: PipelineItem | None) -> dict[str, Any] | None:
    if not pipeline or not pipeline.project_room:
        return None
    room = pipeline.project_room
    tasks = ProjectRoomTask.objects.filter(project_room=room).select_related("assigned_to").order_by("status", "sort_order", "due_date", "id")
    notes = ProjectRoomNote.objects.filter(project_room=room).select_related("author").order_by("-updated_at")[:12]
    activity = ProjectRoomActivity.objects.filter(project_room=room).select_related("actor").order_by("-created_at")[:20]
    return {
        "id": room.id,
        "name": room.name,
        "href": f"/project-rooms/{room.id}",
        "tasks": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "priority": row.priority,
                "due_date": _iso(row.due_date),
                "visibility": row.visibility,
                "assigned_to": row.assigned_to.get_full_name() or row.assigned_to.email if row.assigned_to else "Unassigned",
            }
            for row in tasks[:30]
        ],
        "notes": [
            {
                "id": row.id,
                "title": row.title,
                "body": row.body,
                "visibility": row.visibility,
                "author": row.author.get_full_name() or row.author.email if row.author else "Unknown",
                "updated_at": _iso(row.updated_at),
            }
            for row in notes
        ],
        "activity": [
            {
                "id": row.id,
                "action": row.action,
                "summary": row.summary,
                "visibility": row.visibility,
                "actor": row.actor.get_full_name() or row.actor.email if row.actor else "System",
                "created_at": _iso(row.created_at),
            }
            for row in activity
        ],
    }


def build_capture_command_center(*, organization, opportunity) -> dict[str, Any]:
    assessment = build_capture_assessment(organization=organization, opportunity=opportunity, include_ai=False)
    win = build_win_strategy(organization=organization, opportunity=opportunity)
    pipeline = PipelineItem.objects.filter(organization=organization, opportunity=opportunity).select_related("project_room", "owner").order_by("-updated_at").first()
    room = _project_room_payload(pipeline)

    org_tasks = Task.objects.filter(organization=organization, pipeline_item=pipeline).select_related("assigned_to").order_by("completed", "due_at", "id") if pipeline else Task.objects.none()
    analyses = OpportunityAnalysis.objects.filter(organization=organization, opportunity=opportunity).order_by("-updated_at")[:10]

    memory: list[dict[str, Any]] = []
    if pipeline and pipeline.notes:
        memory.append({"type": "pipeline", "title": "Pipeline notes", "content": pipeline.notes, "updated_at": _iso(pipeline.updated_at)})
    if room:
        for note in room["notes"][:8]:
            memory.append({"type": "project_room_note", "title": note["title"], "content": note["body"], "updated_at": note["updated_at"], "visibility": note["visibility"]})
    for analysis in analyses:
        memory.append({
            "type": "ai_analysis",
            "title": analysis.get_analysis_type_display(),
            "content": analysis.content,
            "updated_at": _iso(analysis.updated_at),
            "model": analysis.model,
        })
    memory.sort(key=lambda row: row.get("updated_at") or "", reverse=True)

    timeline: list[dict[str, Any]] = []
    for row in assessment.get("timeline", []):
        timeline.append({**row, "category": "acquisition"})
    if pipeline:
        timeline.append({"label": f"Pipeline stage: {pipeline.get_stage_display()}", "date": _iso(pipeline.updated_at), "source": "ForgeGov Pipeline", "kind": "platform", "category": "capture"})
    if room:
        for row in room["activity"][:12]:
            timeline.append({"label": row["summary"], "date": row["created_at"], "source": "Project Room", "kind": "platform", "category": "collaboration"})
    timeline.sort(key=lambda row: str(row.get("date") or ""), reverse=True)

    proposal_tasks: list[dict[str, Any]] = []
    for row in org_tasks[:30]:
        proposal_tasks.append({
            "id": f"task-{row.id}",
            "title": row.title,
            "status": "complete" if row.completed else "open",
            "priority": "medium",
            "due_at": _iso(row.due_at),
            "source": "Workspace task",
            "assigned_to": row.assigned_to.get_full_name() or row.assigned_to.email if row.assigned_to else "Unassigned",
        })
    if room:
        for row in room["tasks"]:
            proposal_tasks.append({
                "id": f"room-{row['id']}",
                "title": row["title"],
                "status": row["status"],
                "priority": row["priority"],
                "due_at": row["due_date"],
                "source": "Project Room",
                "assigned_to": row["assigned_to"],
            })

    recommended = [*assessment.get("actions", []), *win.get("recommended_actions", [])]
    dedup: dict[str, dict[str, Any]] = {}
    for row in recommended:
        key = str(row.get("title") or "").strip().lower()
        if key and key not in dedup:
            dedup[key] = row
    next_actions = sorted(dedup.values(), key=lambda row: _priority_rank(row.get("priority", "medium")))[:12]

    readiness = assessment.get("readiness", [])
    compliance = win.get("compliance_matrix", [])
    readiness_missing = sum(1 for row in readiness if row.get("status") != "complete")
    compliance_missing = sum(1 for row in compliance if row.get("status") == "missing")
    open_tasks = sum(1 for row in proposal_tasks if row.get("status") not in {"complete", "completed", "done"})

    return {
        "generated_at": timezone.now().isoformat(),
        "opportunity": assessment.get("opportunity", {}),
        "scores": assessment.get("scores", {}),
        "bid_decision": assessment.get("bid_decision", {}),
        "summary": assessment.get("executive_summary", ""),
        "ai_brief": assessment.get("ai_brief"),
        "health": {
            "readiness_gaps": readiness_missing,
            "compliance_missing": compliance_missing,
            "open_tasks": open_tasks,
            "competitor_signals": len(win.get("competitors", [])),
            "teaming_matches": len(win.get("teaming_recommendations", [])),
        },
        "next_actions": next_actions,
        "risks": assessment.get("risks", []),
        "readiness": readiness,
        "competition": {
            "incumbent": win.get("incumbent", {}),
            "competitors": win.get("competitors", [])[:6],
            "similar_contracts": win.get("similar_contracts", [])[:6],
        },
        "teaming": win.get("teaming_recommendations", [])[:8],
        "compliance": compliance[:50],
        "pricing_readiness": win.get("pricing_readiness", {}),
        "win_strategy": win.get("win_strategy", {}),
        "timeline": timeline[:30],
        "proposal_tasks": proposal_tasks[:40],
        "capture_memory": memory[:20],
        "project_room": room,
        "links": {
            "executive_capture": "capture",
            "win_strategy": "win_strategy",
            "project_room": room.get("href") if room else None,
            "pipeline": "/capture/pipelines",
            "award_intelligence": "/intelligence/awards",
            "network": "/network",
        },
        "labels": {
            "official": "Official government data",
            "derived": "ForgeGov decision-support inference",
            "platform": "ForgeGov workspace data",
        },
        "warnings": [
            "Win probability and bid recommendation are decision-support scores, not guaranteed outcomes.",
            "Likely competitors and incumbent signals are derived from historical award evidence unless explicitly confirmed.",
        ],
    }
