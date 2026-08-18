from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

from .models import (
    AuditLog,
    Membership,
    Organization,
    ProjectRoom,
    ProjectRoomMember,
    ProjectRoomPartner,
)
from .permissions import active_membership
from .security_services import org_security_policy, recent_step_up, session_from_token


FINANCIAL_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.PRICING,
}
PROPOSAL_WRITE_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.CAPTURE,
    Membership.Role.PROPOSAL,
    Membership.Role.CONTRIBUTOR,
}
PROPOSAL_READ_ROLES = PROPOSAL_WRITE_ROLES | {
    Membership.Role.BD,
    Membership.Role.VIEWER,
}
SUBMISSION_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.PROPOSAL,
}
EXECUTIVE_FINANCIAL_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.PRICING,
}
COMPANY_ADMIN_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}
EXPORT_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.CAPTURE,
    Membership.Role.PROPOSAL,
    Membership.Role.PRICING,
}
SENSITIVE_DOCUMENT_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.CAPTURE,
    Membership.Role.PROPOSAL,
    Membership.Role.PRICING,
}


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def audit_denied(
    request,
    *,
    organization: Organization | None,
    capability: str,
    object_type: str = "",
    object_id: str | int = "",
    reason: str = "insufficient_role",
):
    """Record a denied sensitive access without leaking target-tenant details."""
    try:
        AuditLog.objects.create(
            organization=organization,
            actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            action="security.access_denied",
            object_type=object_type,
            object_id=str(object_id or ""),
            metadata={
                "capability": capability,
                "reason": reason,
                "method": request.method,
                "path": request.path[:500],
            },
            ip_address=client_ip(request),
        )
    except Exception:
        # Authorization must fail closed even if audit persistence is degraded.
        pass


def membership_capabilities(membership: Membership | None) -> dict[str, bool]:
    role = membership.role if membership else None
    return {
        "company_admin": role in COMPANY_ADMIN_ROLES,
        "financial_read": role in FINANCIAL_ROLES,
        "financial_write": role in FINANCIAL_ROLES,
        "proposal_read": role in PROPOSAL_READ_ROLES,
        "proposal_write": role in PROPOSAL_WRITE_ROLES,
        "submission_control": role in SUBMISSION_ROLES,
        "executive_financial": role in EXECUTIVE_FINANCIAL_ROLES,
        "project_room_manage": role in COMPANY_ADMIN_ROLES,
        "export_data": role in EXPORT_ROLES,
        "sensitive_documents": role in SENSITIVE_DOCUMENT_ROLES,
    }


class RoleCapabilityPermission(BasePermission):
    capability = "workspace"
    allowed_read_roles: set[str] = set()
    allowed_write_roles: set[str] = set()

    def has_permission(self, request, view):
        membership = active_membership(request.user)
        if not membership:
            return False
        allowed = self.allowed_read_roles if request.method in SAFE_METHODS else self.allowed_write_roles
        if membership.role in allowed:
            return True
        audit_denied(
            request,
            organization=membership.organization,
            capability=self.capability,
            reason=f"role:{membership.role}",
        )
        return False


class IsFinancialMember(RoleCapabilityPermission):
    capability = "financial_sensitive"
    allowed_read_roles = FINANCIAL_ROLES
    allowed_write_roles = FINANCIAL_ROLES


class IsProposalMember(RoleCapabilityPermission):
    capability = "proposal"
    allowed_read_roles = PROPOSAL_READ_ROLES
    allowed_write_roles = PROPOSAL_WRITE_ROLES


class IsSubmissionController(RoleCapabilityPermission):
    capability = "submission_control"
    allowed_read_roles = PROPOSAL_READ_ROLES
    allowed_write_roles = SUBMISSION_ROLES


class IsExecutiveFinancialMember(RoleCapabilityPermission):
    capability = "executive_financial"
    allowed_read_roles = EXECUTIVE_FINANCIAL_ROLES
    allowed_write_roles = EXECUTIVE_FINANCIAL_ROLES


class IsExportMember(RoleCapabilityPermission):
    capability = "export_data"
    allowed_read_roles = EXPORT_ROLES
    allowed_write_roles = EXPORT_ROLES


def role_capability_matrix() -> dict[str, dict[str, bool]]:
    return {
        role: membership_capabilities(type("MembershipRole", (), {"role": role})())
        for role, _ in Membership.Role.choices
    }


def enforce_governance_step_up(request, *, purpose: str, organization: Organization | None = None):
    membership = active_membership(request.user)
    organization = organization or (membership.organization if membership else None)
    if not organization:
        raise PermissionDenied("A valid workspace membership is required.")
    policy = org_security_policy(organization)
    required = (
        bool(policy.require_mfa_for_exports) if purpose == "export"
        else bool(policy.require_mfa_for_project_room_admin) if purpose == "project_room_admin"
        else False
    )
    if not required:
        return
    session = session_from_token(request.auth, user=request.user)
    if not recent_step_up(session):
        audit_denied(
            request,
            organization=organization,
            capability=f"{purpose}_step_up",
            reason="recent_authentication_required",
        )
        raise PermissionDenied("Recent authentication is required for this protected action.")


@dataclass(frozen=True)
class ProjectRoomAccess:
    room: ProjectRoom
    organization: Organization
    owner: bool
    partner: ProjectRoomPartner | None
    member: ProjectRoomMember | None

    @property
    def can_manage(self) -> bool:
        return self.owner and bool(self.member and self.member.role == ProjectRoomMember.Role.MANAGER)

    @property
    def can_contribute(self) -> bool:
        if self.owner:
            return bool(self.member and self.member.role in {ProjectRoomMember.Role.MANAGER, ProjectRoomMember.Role.CONTRIBUTOR})
        return bool(self.partner and self.partner.access_level != ProjectRoomPartner.AccessLevel.VIEWER)

    @property
    def can_view_pricing(self) -> bool:
        if self.owner:
            return bool(self.member and self.member.membership.role in FINANCIAL_ROLES)
        return bool(self.partner and self.partner.can_view_pricing)

    @property
    def can_view_sensitive_documents(self) -> bool:
        if self.owner:
            return bool(self.member and self.member.membership.role in SENSITIVE_DOCUMENT_ROLES)
        return bool(self.partner and self.partner.can_view_sensitive_documents)

    @property
    def can_export(self) -> bool:
        if self.owner:
            return bool(self.member and self.member.membership.role in EXPORT_ROLES)
        return bool(
            self.partner
            and self.partner.can_export
            and self.member
            and self.member.role != ProjectRoomMember.Role.VIEWER
        )

    @property
    def can_upload(self) -> bool:
        if self.owner:
            return self.can_contribute
        return bool(
            self.partner
            and self.member
            and self.member.role in {ProjectRoomMember.Role.MANAGER, ProjectRoomMember.Role.CONTRIBUTOR}
            and self.partner.access_level != ProjectRoomPartner.AccessLevel.VIEWER
            and self.partner.can_upload
        )

    @property
    def can_comment(self) -> bool:
        if self.owner:
            return self.can_contribute
        return bool(
            self.partner
            and self.member
            and self.member.role in {ProjectRoomMember.Role.MANAGER, ProjectRoomMember.Role.CONTRIBUTOR}
            and self.partner.access_level != ProjectRoomPartner.AccessLevel.VIEWER
            and self.partner.can_comment
        )


def accessible_project_rooms(request):
    """Project Rooms the current user may discover in navigation/search."""
    membership = active_membership(request.user)
    if not membership:
        return ProjectRoom.objects.none()
    organization = membership.organization

    owner_filter = Q(owner_organization=organization)
    partner_filter = Q(partners__organization=organization, partners__revoked_at__isnull=True) & (
        Q(partners__expires_at__isnull=True) | Q(partners__expires_at__gt=timezone.now())
    )
    if membership.role not in COMPANY_ADMIN_ROLES:
        owner_filter &= Q(members__membership=membership)
        partner_filter &= Q(members__membership=membership)

    return ProjectRoom.objects.filter(
        owner_filter | partner_filter,
        deleted_at__isnull=True,
    ).distinct()


def project_room_access(request, room_id: int) -> ProjectRoomAccess | None:
    """
    Resolve collaboration access from the *current active membership*.

    A partner organization being on a room is not sufficient for an owner-company
    user: owner-company users must be explicitly added to the room. Partner
    companies use their organization-level partner grant.
    """
    membership = active_membership(request.user)
    if not membership:
        return None
    organization = membership.organization

    room = ProjectRoom.objects.filter(
        Q(owner_organization=organization) | Q(partners__organization=organization),
        pk=room_id,
        deleted_at__isnull=True,
    ).select_related("owner_organization").distinct().first()
    if not room:
        audit_denied(
            request,
            organization=organization,
            capability="project_room",
            object_type="project_room",
            object_id=room_id,
            reason="tenant_boundary",
        )
        return None

    owner = room.owner_organization_id == organization.id
    member = None
    partner = None
    if owner:
        member = ProjectRoomMember.objects.filter(
            project_room=room,
            membership=membership,
        ).first()
        # Owners/admins retain administrative recovery access even if a legacy
        # room predates explicit ProjectRoomMember rows.
        if not member and membership.role in COMPANY_ADMIN_ROLES:
            member = ProjectRoomMember(
                project_room=room,
                membership=membership,
                role=ProjectRoomMember.Role.MANAGER,
            )
        elif not member:
            audit_denied(
                request,
                organization=organization,
                capability="project_room",
                object_type="project_room",
                object_id=room_id,
                reason="owner_member_not_assigned",
            )
            return None
    else:
        partner = ProjectRoomPartner.objects.filter(
            project_room=room,
            organization=organization,
            revoked_at__isnull=True,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
        if not partner:
            audit_denied(
                request,
                organization=organization,
                capability="project_room",
                object_type="project_room",
                object_id=room_id,
                reason="partner_access_expired_or_revoked",
            )
            return None
        member = ProjectRoomMember.objects.filter(
            project_room=room,
            membership=membership,
        ).first()
        if not member and membership.role in COMPANY_ADMIN_ROLES:
            # Partner company owners/admins retain recovery access and can enroll
            # their own employees into the collaboration room.
            member = ProjectRoomMember(
                project_room=room,
                membership=membership,
                role=ProjectRoomMember.Role.MANAGER,
            )
        elif not member:
            audit_denied(
                request,
                organization=organization,
                capability="project_room",
                object_type="project_room",
                object_id=room_id,
                reason="partner_member_not_assigned",
            )
            return None

    return ProjectRoomAccess(
        room=room,
        organization=organization,
        owner=owner,
        partner=partner,
        member=member,
    )


def filter_project_room_visibility(
    queryset,
    access: ProjectRoomAccess,
    *,
    allow_pricing: bool = False,
    allow_sensitive: bool = False,
):
    visibilities = ["shared"]
    if access.owner:
        visibilities.append("internal")
    if allow_pricing and access.can_view_pricing:
        visibilities.append("pricing")
    if allow_sensitive and access.can_view_sensitive_documents:
        visibilities.append("sensitive")
    return queryset.filter(visibility__in=visibilities)
