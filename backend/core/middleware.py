from django.http import JsonResponse


class RenderHealthCheckMiddleware:
    """Return a lightweight health response before host/security middleware.

    Render sends health checks with a verified custom domain as the Host header.
    This endpoint must remain reachable while custom-domain environment values are
    being updated during a Blueprint sync. All non-health requests continue through
    Django's normal host, security, CORS, authentication, and CSRF validation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/api/health/":
            return JsonResponse({
                "status": "ok",
                "service": "forgegov-api",
                "product": "ForgeGov",
                "version": "2.6.1",
            })
        return self.get_response(request)
