from __future__ import annotations

import base64
import hashlib

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import CompanyLogo, Membership, Organization

MAX_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}


def _detect_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _logo_response(logo: CompanyLogo):
    response = HttpResponse(bytes(logo.content), content_type=logo.content_type)
    response["Cache-Control"] = "public, max-age=300"
    response["ETag"] = f'"{logo.sha256}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def company_logo_public(request, organization_id: int):
    logo = CompanyLogo.objects.filter(organization_id=organization_id).first()
    if not logo:
        return Response({"detail": "Company logo not found."}, status=404)
    if request.headers.get("If-None-Match") == f'"{logo.sha256}"':
        return HttpResponse(status=304)
    return _logo_response(logo)


@api_view(["GET"])
@permission_classes([AllowAny])
def company_logo_public_by_name(request):
    name = str(request.query_params.get("name") or "").strip()
    if not name:
        return Response({"detail": "Company name is required."}, status=400)
    logo = (
        CompanyLogo.objects
        .filter(organization__name__iexact=name)
        .select_related("organization")
        .order_by("-updated_at", "-id")
        .first()
    )
    if not logo:
        return Response({"detail": "Company logo not found."}, status=404)
    return _logo_response(logo)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def company_logo_manage(request):
    from .views import _request_organization

    organization = _request_organization(request)
    membership = Membership.objects.filter(organization=organization, user=request.user).first()
    if not membership or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return Response({"detail": "Company owner or administrator access is required."}, status=403)

    if bool(request.data.get("remove")):
        CompanyLogo.objects.filter(organization=organization).delete()
        return Response({"removed": True, "organization_id": organization.id})

    content_type = str(request.data.get("content_type") or "").strip().lower()
    encoded = str(request.data.get("content_base64") or "").strip()
    if content_type not in ALLOWED_TYPES:
        return Response({"detail": "Logo must be PNG, JPEG, or WebP."}, status=400)
    if not encoded:
        return Response({"detail": "Logo image content is required."}, status=400)

    try:
        content = base64.b64decode(encoded, validate=True)
    except Exception:
        return Response({"detail": "Logo image encoding is invalid."}, status=400)

    if not content or len(content) > MAX_LOGO_BYTES:
        return Response({"detail": "Logo must be 2 MB or smaller."}, status=400)

    detected = _detect_type(content)
    if detected != content_type:
        return Response({"detail": "Logo content does not match the declared image type."}, status=400)

    digest = hashlib.sha256(content).hexdigest()
    logo, _ = CompanyLogo.objects.update_or_create(
        organization=organization,
        defaults={"content": content, "content_type": detected, "sha256": digest},
    )
    return Response({
        "organization_id": organization.id,
        "content_type": logo.content_type,
        "sha256": logo.sha256,
        "logo_url": f"/api/network/organizations/{organization.id}/logo/",
        "updated_at": logo.updated_at.isoformat(),
    })
