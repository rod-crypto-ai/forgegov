from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


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

    def authenticate(self, request):
        header_result = super().authenticate(request)

        if header_result is not None:
            user, token = header_result
            raw_org = request.headers.get("X-ForgeGov-Organization") or request.COOKIES.get("forgegov_workspace")
            if raw_org and str(raw_org).isdigit():
                user._forgegov_organization_id = int(raw_org)
            return user, token

        raw_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE_NAME)

        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        enforce_csrf(request)

        user = self.get_user(validated_token)
        raw_org = request.headers.get("X-ForgeGov-Organization") or request.COOKIES.get("forgegov_workspace")
        if raw_org and str(raw_org).isdigit():
            user._forgegov_organization_id = int(raw_org)
        return user, validated_token
