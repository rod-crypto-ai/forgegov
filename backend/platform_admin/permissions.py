from rest_framework.permissions import BasePermission

from .models import PlatformAdminGrant


def active_platform_grant(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return "super_admin"
    try:
        grant = user.forgegov_platform_admin_grant
    except PlatformAdminGrant.DoesNotExist:
        return None
    if not grant.is_active or not grant.mfa_verified:
        return None
    return grant.role


class IsPlatformAdmin(BasePermission):
    message = "ForgeGov platform administrator access is required."

    def has_permission(self, request, view):
        return active_platform_grant(request.user) is not None


class IsPlatformSuperAdmin(BasePermission):
    message = "ForgeGov Platform Super Admin access is required."

    def has_permission(self, request, view):
        return active_platform_grant(request.user) == "super_admin"
