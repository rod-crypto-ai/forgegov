from rest_framework.permissions import BasePermission

from .models import PlatformAdminGrant


def active_platform_grant(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        grant = user.forgegov_platform_admin_grant
    except PlatformAdminGrant.DoesNotExist:
        grant = None
    if grant and grant.is_active and grant.mfa_verified:
        return grant.role
    if getattr(user, "is_superuser", False):
        return "super_admin"
    return None


class IsPlatformAdmin(BasePermission):
    message = "ForgeGov platform administrator access is required."

    def has_permission(self, request, view):
        return active_platform_grant(request.user) is not None


class IsPlatformSuperAdmin(BasePermission):
    message = "ForgeGov Platform Super Admin access is required."

    def has_permission(self, request, view):
        return active_platform_grant(request.user) in {"creator", "super_admin"}


class IsPlatformCreator(BasePermission):
    message = "ForgeGov Creator / Platform Owner access is required."

    def has_permission(self, request, view):
        return active_platform_grant(request.user) == "creator"
