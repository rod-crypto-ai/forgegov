from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

try:
    from django.middleware.csrf import CSRFCheck
except ImportError:  # pragma: no cover
    CSRFCheck = None


def enforce_csrf(request) -> None:
    """Require Django's CSRF cookie/header pair for unsafe cookie-auth requests."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    if CSRFCheck is None:
        raise PermissionDenied("CSRF validation is unavailable.")
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate by Authorization header or secure HttpOnly access cookie."""

    def authenticate(self, request):
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        raw_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE_NAME)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        enforce_csrf(request)
        return self.get_user(validated_token), validated_token
