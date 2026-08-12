from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Membership, Organization


def active_membership(user):
    if not user or not user.is_authenticated:
        return None
    queryset = user.organization_memberships.filter(
        active=True,
    ).exclude(
        organization__status__in=[Organization.Status.SUSPENDED, Organization.Status.CANCELLED],
    ).select_related("organization")
    preferred = getattr(user, "_forgegov_organization_id", None)
    if preferred:
        selected = queryset.filter(organization_id=preferred).first()
        if selected:
            return selected
    return queryset.order_by("id").first()


class IsOrganizationMember(BasePermission):
    def has_permission(self, request, view):
        return active_membership(request.user) is not None


class IsOrganizationAdmin(BasePermission):
    def has_permission(self, request, view):
        membership = active_membership(request.user)
        return bool(membership and membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN})


class ReadOnlyOrContributor(BasePermission):
    def has_permission(self, request, view):
        membership = active_membership(request.user)
        if not membership:
            return False
        if request.method in SAFE_METHODS:
            return True
        return membership.role != Membership.Role.VIEWER
