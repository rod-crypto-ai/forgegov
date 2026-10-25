from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import AuthSession, UserSecurityProfile


class CSRFCheck(CsrfViewMiddleware):
    """
    Run Django CSRF validation without returning an HTML response.
    Return the rejection reason so the API can provide a JSON error.
    """

    def _reject(self, request, reason):
        return reason


def enforce_csrf(request) -> None:
    """Require Django's CSRF cookie/header pair for unsafe cookie-auth requests."""

    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return

    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})

    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate using an Authorization header or secure HttpOnly cookie."""

    def _enforce_account_state(self, user):
        try:
            profile = user.forgegov_security
        except UserSecurityProfile.DoesNotExist:
            return
        if profile.account_status != UserSecurityProfile.AccountStatus.ACTIVE:
            raise AuthenticationFailed("Account access is unavailable.")

    def _enforce_session_state(self, user, token):
        sid = token.get("fgsid") if token is not None else None
        if not sid:
            return
        exists = AuthSession.objects.filter(
            session_id=sid,
            user=user,
            revoked_at__isnull=True,
            expires_at__gt=__import__("django.utils.timezone", fromlist=["now"]).now(),
        ).exists()
        if not exists:
            raise AuthenticationFailed("Session has been revoked or expired.")

    def authenticate(self, request):
        header_result = super().authenticate(request)

        if header_result is not None:
            user, token = header_result
            self._enforce_account_state(user)
            self._enforce_session_state(user, token)
            raw_org = request.headers.get("X-ForgeGov-Organization") or request.COOKIES.get("forgegov_workspace")
            if raw_org and str(raw_org).isdigit():
                user._forgegov_organization_id = int(raw_org)
            enforce_subscription(request, user)
            return user, token

        raw_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE_NAME)

        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        enforce_csrf(request)

        user = self.get_user(validated_token)
        self._enforce_account_state(user)
        self._enforce_session_state(user, validated_token)
        raw_org = request.headers.get("X-ForgeGov-Organization") or request.COOKIES.get("forgegov_workspace")
        if raw_org and str(raw_org).isdigit():
            user._forgegov_organization_id = int(raw_org)
        enforce_subscription(request, user)
        return user, validated_token


# Exact recovery endpoints: never exempt the whole auth or billing namespace.
SUBSCRIPTION_RECOVERY_PATHS = frozenset({
    "/api/auth/me/", "/api/auth/workspaces/", "/api/auth/logout/",
    "/api/auth/csrf/", "/api/auth/refresh/", "/api/auth/login/",
    "/api/auth/register/", "/api/auth/registration-config/",
    "/api/auth/verify-email/", "/api/auth/resend-verification/",
    "/api/billing/summary/", "/api/billing/checkout/", "/api/billing/portal/",
    "/api/health/", "/api/ready/", "/api/public/inquiries/",
})


def enforce_subscription(request, user):
    from .permissions import active_membership
    from .subscriptions import ensure_organization_subscription
    # Account security remains available to locked workspaces.
    if (request.path in SUBSCRIPTION_RECOVERY_PATHS
            or request.path.startswith("/api/auth/security/")
            or request.path.startswith("/api/auth/mfa/")
            or request.path.startswith("/api/auth/invitations/")):
        return
    if request.path.startswith("/api/platform-admin/"):
        from platform_admin.permissions import active_platform_grant
        if active_platform_grant(user):
            return
    membership = active_membership(user)
    if not membership or not ensure_organization_subscription(membership.organization).permits_access:
        raise PermissionDenied({
            "detail": "An active subscription is required. Open Billing or contact your workspace administrator.",
            "code": "subscription_required",
        })


class SubscriptionSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, token = result
            raw_org = request.headers.get("X-ForgeGov-Organization") or request.COOKIES.get("forgegov_workspace")
            if raw_org and str(raw_org).isdigit():
                user._forgegov_organization_id = int(raw_org)
            enforce_subscription(request, user)
        return result
