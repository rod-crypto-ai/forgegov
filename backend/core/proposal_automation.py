from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .ai import OpenAIIntegrationError, ask_ai
from .models import (
    Membership,
    OpportunityDocument,
    OpportunityDocumentChunk,
    ProposalFinding,
    ProposalLibraryEntry,
    ProposalPlan,
    ProposalRequirement,
    ProposalReview,
    ProposalSection,
    ProposalSectionRequirement,
    ProposalSectionRevision,
    ProposalVolume,
)
from .proposal_execution import ensure_proposal_execution, proposal_execution_payload


DEFAULT_STRUCTURE = [
    {
        "key": "volume-1-technical-management",
        "title": "Volume I — Technical & Management",
        "sections": [
            ("executive-summary", "Executive Summary", ProposalSection.SectionType.COVER),
            ("technical-approach", "Technical Approach", ProposalSection.SectionType.TECHNICAL),
            ("management-staffing", "Management & Staffing Approach", ProposalSection.SectionType.MANAGEMENT),
        ],
    },
    {
        "key": "volume-2-past-performance",
        "title": "Volume II — Past Performance",
        "sections": [
            ("past-performance", "Past Performance", ProposalSection.SectionType.PAST_PERFORMANCE),
        ],
    },
    {
        "key": "volume-3-price",
        "title": "Volume III — Price / Cost",
        "sections": [
            ("pricing", "Price / Cost Narrative", ProposalSection.SectionType.PRICING),
        ],
    },
]


def _display_user(user) -> str:
    if not user:
        return ""
    return user.get_full_name() or user.username


def _valid_member(organization, user_id) -> bool:
    return bool(user_id and Membership.objects.filter(organization=organization, user_id=user_id, active=True).exists())


def ensure_proposal_production(*, organization, opportunity, user=None) -> ProposalPlan:
    plan = ensure_proposal_execution(organization=organization, opportunity=opportunity, user=user)
    for volume_order, definition in enumerate(DEFAULT_STRUCTURE):
        volume, _ = ProposalVolume.objects.get_or_create(
            plan=plan,
            key=definition["key"],
            defaults={"title": definition["title"], "sort_order": volume_order},
        )
        for section_order, (key, title, section_type) in enumerate(definition["sections"]):
            section, created = ProposalSection.objects.get_or_create(
                volume=volume,
                key=key,
                defaults={
                    "title": title,
                    "section_type": section_type,
                    "sort_order": section_order,
                },
            )
            if created:
                _seed_requirement_links(section)
    return plan


def _seed_requirement_links(section: ProposalSection) -> None:
    requirements = list(section.volume.plan.requirements.all())
    key = section.key.lower()
    for requirement in requirements:
        rkey = requirement.key.lower()
        link = False
        if key == "technical-approach":
            link = any(token in rkey for token in ("section-l", "section-m", "deliverables", "security", "clauses"))
        elif key == "management-staffing":
            link = any(token in rkey for token in ("section-l", "deliverables", "security"))
        elif key == "pricing":
            link = any(token in rkey for token in ("clins", "section-l"))
        elif key == "past-performance":
            link = "section-m" in rkey
        elif key == "executive-summary":
            link = "section-m" in rkey
        if link:
            ProposalSectionRequirement.objects.get_or_create(section=section, requirement=requirement)


def _section_sources(section: ProposalSection, organization, opportunity) -> tuple[list[dict[str, Any]], list[OpportunityDocumentChunk]]:
    links = list(section.requirement_links.select_related("requirement").all())
    requirement_rows = [
        {
            "id": link.requirement_id,
            "key": link.requirement.key,
            "requirement": link.requirement.requirement,
            "source": link.requirement.source,
            "evidence": link.requirement.evidence,
            "status": link.requirement.status,
        }
        for link in links
    ]
    terms: list[str] = [section.title]
    for row in requirement_rows:
        terms.extend(str(row.get("requirement") or "").split()[:6])
    term_candidates = [term.strip(".,:;()[]").lower() for term in terms for term in str(term).split() if len(term.strip(".,:;()[]")) >= 5]
    chunks = OpportunityDocumentChunk.objects.filter(
        document__organization=organization,
        document__opportunity=opportunity,
        document__status=OpportunityDocument.Status.READY,
    ).select_related("document")
    match = Q()
    for term in term_candidates[:8]:
        match |= Q(text__icontains=term)
    selected = list((chunks.filter(match) if match.children else chunks).order_by("document_id", "ordinal")[:16])
    if not selected:
        selected = list(chunks.order_by("document_id", "ordinal")[:16])
    return requirement_rows, selected


def _source_snapshot(section: ProposalSection, requirement_rows, chunks, *, library_ids=None, ai_sources=None) -> dict[str, Any]:
    return {
        "section_id": section.id,
        "requirements": requirement_rows,
        "documents": [
            {
                "document_id": chunk.document_id,
                "file_name": chunk.document.file_name,
                "checksum": chunk.document.checksum,
                "page_number": chunk.page_number,
                "chunk_id": chunk.id,
            }
            for chunk in chunks
        ],
        "library_entry_ids": list(library_ids or []),
        "ai_sources": list(ai_sources or []),
        "captured_at": timezone.now().isoformat(),
    }


def _next_revision(section: ProposalSection) -> int:
    return int(section.revisions.aggregate(value=Max("revision"))["value"] or 0) + 1


def save_section_revision(*, section: ProposalSection, content: str, user, change_summary: str = "", ai_generated: bool = False, provider: str = "", model: str = "", source_snapshot=None) -> ProposalSectionRevision:
    return ProposalSectionRevision.objects.create(
        section=section,
        revision=_next_revision(section),
        content=content,
        change_summary=str(change_summary or "")[:1000],
        source_snapshot=source_snapshot or {},
        ai_generated=ai_generated,
        provider=str(provider or "")[:80],
        model=str(model or "")[:120],
        created_by=user,
    )


def _section_payload(section: ProposalSection, *, can_financial: bool) -> dict[str, Any]:
    restricted = section.section_type == ProposalSection.SectionType.PRICING and not can_financial
    links = [] if restricted else list(section.requirement_links.select_related("requirement").all())
    return {
        "id": section.id,
        "key": section.key,
        "title": section.title,
        "section_type": section.section_type,
        "instructions": "" if restricted else section.instructions,
        "content": "" if restricted else section.content,
        "status": section.status,
        "owner_id": section.owner_id,
        "owner": _display_user(section.owner),
        "due_at": section.due_at.isoformat() if section.due_at else None,
        "sort_order": section.sort_order,
        "approved_at": section.approved_at.isoformat() if section.approved_at else None,
        "approved_by": _display_user(section.approved_by),
        "revision_count": section.revisions.count() if not restricted else 0,
        "restricted": restricted,
        "requirement_links": [
            {
                "link_id": link.id,
                "requirement_id": link.requirement_id,
                "key": link.requirement.key,
                "requirement": link.requirement.requirement,
                "status": link.requirement.status,
                "source": link.requirement.source,
            }
            for link in links
        ],
    }


def package_validation(*, plan: ProposalPlan, can_financial: bool = True) -> dict[str, Any]:
    volumes = list(plan.volumes.prefetch_related("sections").all())
    sections = [section for volume in volumes for section in volume.sections.all()]
    requirements = list(plan.requirements.all())
    reviews = list(plan.reviews.all())
    findings = list(plan.findings.all())
    blockers: list[str] = []
    warnings: list[str] = []
    if not volumes:
        blockers.append("No proposal volumes exist.")
    if not sections:
        blockers.append("No proposal sections exist.")
    incomplete_sections = [s.title for s in sections if s.status not in {ProposalSection.Status.APPROVED, ProposalSection.Status.LOCKED}]
    if incomplete_sections:
        blockers.append(f"{len(incomplete_sections)} proposal section(s) are not approved or locked.")
    empty_sections = [s.title for s in sections if not s.content.strip()]
    if empty_sections:
        blockers.append(f"{len(empty_sections)} proposal section(s) are empty.")
    open_requirements = [r for r in requirements if r.status not in {ProposalRequirement.Status.COMPLIANT, ProposalRequirement.Status.NOT_APPLICABLE}]
    if open_requirements:
        blockers.append(f"{len(open_requirements)} compliance requirement(s) remain open.")
    unlinked = [r for r in requirements if not r.section_links.exists()]
    if unlinked:
        warnings.append(f"{len(unlinked)} compliance requirement(s) are not mapped to a proposal section.")
    failed_reviews = [r for r in reviews if r.status != ProposalReview.Status.PASSED]
    if failed_reviews:
        blockers.append(f"{len(failed_reviews)} proposal review gate(s) have not passed.")
    open_findings = [f for f in findings if f.status == ProposalFinding.Status.OPEN]
    if open_findings:
        blockers.append(f"{len(open_findings)} proposal finding(s) remain open.")
    if not plan.final_submission_verified:
        blockers.append("Final submission method has not been verified.")
    if not can_financial and any(s.section_type == ProposalSection.SectionType.PRICING for s in sections):
        warnings.append("Pricing volume validation details are restricted for the current role.")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "counts": {
            "volumes": len(volumes),
            "sections": len(sections),
            "sections_approved": len(sections) - len(incomplete_sections),
            "requirements": len(requirements),
            "requirements_closed": len(requirements) - len(open_requirements),
            "reviews": len(reviews),
            "reviews_passed": len(reviews) - len(failed_reviews),
            "open_findings": len(open_findings),
        },
        "checked_at": timezone.now().isoformat(),
    }


def production_payload(*, organization, opportunity, user=None, can_financial: bool = False, can_approve: bool = False) -> dict[str, Any]:
    plan = ensure_proposal_production(organization=organization, opportunity=opportunity, user=user)
    execution = proposal_execution_payload(organization=organization, opportunity=opportunity, user=user)
    volumes = []
    for volume in plan.volumes.select_related("owner").prefetch_related("sections__owner", "sections__approved_by", "sections__requirement_links__requirement").all():
        section_rows = [_section_payload(section, can_financial=can_financial) for section in volume.sections.all()]
        volumes.append({
            "id": volume.id,
            "key": volume.key,
            "title": volume.title,
            "instructions": volume.instructions,
            "status": volume.status,
            "owner_id": volume.owner_id,
            "owner": _display_user(volume.owner),
            "due_at": volume.due_at.isoformat() if volume.due_at else None,
            "page_limit": volume.page_limit,
            "sort_order": volume.sort_order,
            "sections": section_rows,
        })
    library_rows = ProposalLibraryEntry.objects.filter(organization=organization).select_related("source_section").order_by("category", "title")[:200]
    library = []
    for row in library_rows:
        pricing_entry = row.category == ProposalSection.SectionType.PRICING or bool(row.source_section and row.source_section.section_type == ProposalSection.SectionType.PRICING)
        if pricing_entry and not can_financial:
            continue
        library.append({
            "id": row.id,
            "title": row.title,
            "category": row.category,
            "content": row.content,
            "tags": row.tags,
            "status": row.status,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "source_section_id": row.source_section_id,
        })
    return {
        "plan": execution.get("plan"),
        "execution": execution,
        "volumes": volumes,
        "library": library,
        "package_validation": package_validation(plan=plan, can_financial=can_financial),
        "permissions": {"can_financial": can_financial, "can_approve": can_approve},
        "warning": "ForgeGov proposal automation is decision support. AI drafts must be reviewed against the current official solicitation and approved by an authorized human before submission.",
    }


@transaction.atomic
def update_section(*, section: ProposalSection, organization, user, payload: dict[str, Any], can_financial: bool, can_approve: bool = False) -> ProposalSection:
    if section.section_type == ProposalSection.SectionType.PRICING and not can_financial:
        raise PermissionError("Financial authorization is required to edit the pricing proposal section.")
    original_content = section.content
    original_status = section.status
    allowed_status = {value for value, _ in ProposalSection.Status.choices}
    requested_status = payload.get("status") if payload.get("status") in allowed_status else None
    content_change_requested = "content" in payload and str(payload.get("content") or "") != section.content
    substantive_change_requested = content_change_requested or "instructions" in payload or "title" in payload
    if original_status == ProposalSection.Status.LOCKED and (substantive_change_requested or (requested_status and requested_status != ProposalSection.Status.LOCKED)) and not can_approve:
        raise PermissionError("Proposal approval authority is required to modify or unlock a locked section.")
    if "title" in payload:
        section.title = str(payload.get("title") or "")[:500] or section.title
    if "instructions" in payload:
        section.instructions = str(payload.get("instructions") or "")
    if "content" in payload:
        section.content = str(payload.get("content") or "")
    if requested_status:
        next_status = requested_status
        if next_status in {ProposalSection.Status.APPROVED, ProposalSection.Status.LOCKED} and not can_approve:
            raise PermissionError("Proposal approval authority is required to approve or lock a section.")
        section.status = next_status
        if next_status in {ProposalSection.Status.APPROVED, ProposalSection.Status.LOCKED}:
            section.approved_at = timezone.now()
            section.approved_by = user
        else:
            section.approved_at = None
            section.approved_by = None
    elif substantive_change_requested and original_status in {ProposalSection.Status.APPROVED, ProposalSection.Status.LOCKED}:
        # Any substantive change invalidates the prior approval unless an authorized
        # approver explicitly re-approves/locks the new content in the same request.
        section.status = ProposalSection.Status.DRAFTING
        section.approved_at = None
        section.approved_by = None
    if "due_at" in payload:
        section.due_at = payload.get("due_at") or None
    if "owner_id" in payload:
        owner_id = payload.get("owner_id")
        if owner_id and not _valid_member(organization, owner_id):
            raise ValueError("Section owner must belong to the active company workspace.")
        section.owner_id = owner_id or None
    section.save()
    if "content" in payload and section.content != original_content:
        requirement_rows, chunks = _section_sources(section, organization, section.volume.plan.opportunity)
        save_section_revision(
            section=section,
            content=section.content,
            user=user,
            change_summary=str(payload.get("change_summary") or "Manual section update"),
            source_snapshot=_source_snapshot(section, requirement_rows, chunks),
        )
    return section


def draft_section(*, section: ProposalSection, organization, opportunity, user, instruction: str = "", can_financial: bool = False, persist: bool = False) -> dict[str, Any]:
    if section.section_type == ProposalSection.SectionType.PRICING and not can_financial:
        raise PermissionError("Financial authorization is required to draft the pricing proposal section.")
    requirement_rows, chunks = _section_sources(section, organization, opportunity)
    library_entries = list(
        ProposalLibraryEntry.objects.filter(organization=organization, status=ProposalLibraryEntry.Status.APPROVED)
        .filter(Q(category=section.section_type) | Q(category="general"))
        .order_by("category", "title")[:5]
    )
    doc_evidence = [
        {
            "label": f"DOC-{index}",
            "file": chunk.document.file_name,
            "page": chunk.page_number,
            "section": chunk.section,
            "text": chunk.text[:1800],
        }
        for index, chunk in enumerate(chunks, 1)
    ]
    approved_content = [
        {"id": row.id, "title": row.title, "category": row.category, "content": row.content[:3500]}
        for row in library_entries
    ]
    evidence = {
        "opportunity": {
            "title": opportunity.title,
            "solicitation_number": opportunity.solicitation_number,
            "agency": opportunity.agency,
            "response_deadline": opportunity.response_deadline.isoformat() if opportunity.response_deadline else None,
        },
        "section": {"title": section.title, "type": section.section_type, "instructions": section.instructions},
        "linked_requirements": requirement_rows,
        "official_document_evidence": doc_evidence,
        "approved_company_content": approved_content,
    }
    prompt = (
        "FORGEGOV PROPOSAL SECTION DRAFTING\n"
        "Draft only from the supplied official solicitation evidence, linked compliance requirements, and approved company content. "
        "Do not invent requirements, customer preferences, past performance, staffing, certifications, metrics, or pricing. "
        "If evidence is insufficient, insert a clear [VALIDATION REQUIRED] note instead of guessing. "
        "Live web material, if the user's ForgeGov settings allow it, may provide background context only and must never be treated as a solicitation requirement or company proof point. "
        "Preserve traceability by citing DOC-* labels and requirement keys inline when they support a statement.\n\n"
        f"USER DRAFTING INSTRUCTION:\n{str(instruction or 'Create a strong first draft for this section using only supported evidence.').strip()[:3000]}\n\n"
        f"SECTION EVIDENCE:\n{json.dumps(evidence, default=str, ensure_ascii=True)[:28000]}"
    )
    public_web_query = " ".join(part for part in [
        opportunity.agency, opportunity.solicitation_number, opportunity.title, section.title, "federal contract"
    ] if part)[:500]
    result = ask_ai(message=prompt, history=[], organization=organization, user=user, web_query=public_web_query)
    answer = str(result.get("answer") or "").strip()
    if not answer:
        raise OpenAIIntegrationError("ForgeGov AI returned no proposal draft.", status_code=502)
    snapshot = _source_snapshot(
        section,
        requirement_rows,
        chunks,
        library_ids=[row.id for row in library_entries],
        ai_sources=result.get("sources") or [],
    )
    revision = None
    if persist:
        section.content = answer
        section.status = ProposalSection.Status.DRAFTING
        section.last_ai_provider = str(result.get("provider") or "")[:80]
        section.last_ai_model = str(result.get("model") or "")[:120]
        section.approved_at = None
        section.approved_by = None
        section.save()
        revision = save_section_revision(
            section=section,
            content=answer,
            user=user,
            change_summary="ForgeAI evidence-grounded draft",
            ai_generated=True,
            provider=result.get("provider") or "",
            model=result.get("model") or "",
            source_snapshot=snapshot,
        )
    return {
        "section_id": section.id,
        "draft": answer,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "sources": result.get("sources") or [],
        "source_snapshot": snapshot,
        "revision_id": revision.id if revision else None,
        "persisted": bool(revision),
        "warning": "AI-generated proposal content is a draft. Validate every claim, citation, requirement, and proof point before approval.",
    }
