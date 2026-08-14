from django.http import JsonResponse

from .models import UserControlState, OrganizationControlState
from .permissions import active_platform_grant
from .services import platform_mode


class PlatformControlMiddleware:
    """
    Global account/maintenance guard.

    User suspension is enforced on every authenticated request.
    Maintenance mode blocks normal authenticated product traffic while allowing
    health/auth endpoints and verified platform administrators.

    Organization suspension is enforced when ForgeGov identifies the workspace by
    X-Organization-ID or X-Workspace-ID. The installer does not guess or replace
    the application's existing tenant resolver.
    """

    SAFE_PREFIXES = (
        "/api/health/",
        "/api/auth/",
        "/api/platform-admin/",
        "/admin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            state = UserControlState.objects.filter(user=user).first()
            if state and state.status in {UserControlState.Status.SUSPENDED, UserControlState.Status.DISABLED}:
                return JsonResponse({"detail": "This ForgeGov account is not active."}, status=403)

            if platform_mode() == "maintenance" and not request.path.startswith(self.SAFE_PREFIXES):
                if active_platform_grant(user) is None:
                    return JsonResponse({"detail": "ForgeGov is temporarily in maintenance mode."}, status=503)

            org_id = request.headers.get("X-Organization-ID") or request.headers.get("X-Workspace-ID")
            if org_id:
                org_state = OrganizationControlState.objects.filter(organization_id=org_id).first()
                if org_state and org_state.status in {
                    OrganizationControlState.Status.REJECTED,
                    OrganizationControlState.Status.SUSPENDED,
                    OrganizationControlState.Status.DISABLED,
                }:
                    return JsonResponse({"detail": "This organization is not active in ForgeGov."}, status=403)

        return self.get_response(request)
