import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .authentication import enforce_csrf
from .models import AuditLog, Invitation, Membership, Organization
from .permissions import IsOrganizationAdmin, active_membership
from .serializers import AuditLogSerializer, InvitationSerializer, MembershipSerializer, UserSerializer
from .throttles import LoginThrottle, RegistrationThrottle

User = get_user_model()


def _cookie_settings():
    secure = not settings.DEBUG
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "None" if secure else "Lax",
        "path": "/",
    }


def _set_auth_cookies(response, user, refresh_token=None):
    refresh_token = refresh_token or RefreshToken.for_user(user)
    access = str(refresh_token.access_token)
    cookie = _cookie_settings()
    response.set_cookie(settings.AUTH_ACCESS_COOKIE_NAME, access, max_age=settings.AUTH_ACCESS_COOKIE_MAX_AGE, **cookie)
    response.set_cookie(settings.AUTH_REFRESH_COOKIE_NAME, str(refresh_token), max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE, **cookie)
    return response


def _clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE_NAME, path="/", samesite="None" if not settings.DEBUG else "Lax")
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/", samesite="None" if not settings.DEBUG else "Lax")
    return response


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def audit(request, action, organization=None, object_type="", object_id="", metadata=None):
    AuditLog.objects.create(
        organization=organization,
        actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        action=action,
        object_type=object_type,
        object_id=str(object_id or ""),
        metadata=metadata or {},
        ip_address=_client_ip(request),
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    enforce_csrf(request)
    email = str(request.data.get("email") or "").strip().lower()
    password = str(request.data.get("password") or "")
    first_name = str(request.data.get("first_name") or "").strip()
    last_name = str(request.data.get("last_name") or "").strip()
    organization_name = str(request.data.get("organization_name") or "").strip()
    invitation_token = str(request.data.get("invitation_token") or "").strip()

    if not email or not password:
        return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email__iexact=email).exists():
        return Response({"detail": "An account already exists for this email."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password)
    except ValidationError as exc:
        return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        invitation = None
        if invitation_token:
            invitation = Invitation.objects.select_for_update().filter(
                token=invitation_token,
                status=Invitation.Status.PENDING,
                expires_at__gt=timezone.now(),
                email__iexact=email,
            ).first()
            if not invitation:
                return Response({"detail": "The invitation is invalid, expired, or belongs to another email."}, status=status.HTTP_400_BAD_REQUEST)
            if invitation.role == Membership.Role.OWNER:
                return Response({"detail": "Owner access cannot be granted through a team invitation."}, status=status.HTTP_400_BAD_REQUEST)

        if not invitation and not settings.PUBLIC_REGISTRATION_ENABLED:
            return Response({"detail": "Registration requires a valid team invitation."}, status=status.HTTP_403_FORBIDDEN)

        username = email
        user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name)
        if invitation:
            organization = invitation.organization
            role = invitation.role
            invitation.status = Invitation.Status.ACCEPTED
            invitation.save(update_fields=["status", "updated_at"])
        else:
            if not organization_name:
                organization_name = f"{first_name or email.split('@')[0]}'s Workspace"
            base_slug = slugify(organization_name) or "workspace"
            slug = base_slug
            suffix = 2
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            organization = Organization.objects.create(name=organization_name, slug=slug)
            role = Membership.Role.OWNER
        Membership.objects.create(organization=organization, user=user, role=role)

    response = Response({
        "user": UserSerializer(user).data,
        "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        "role": role,
    }, status=status.HTTP_201_CREATED)
    audit(request, "auth.register", organization, "user", user.id, {"email": email})
    return _set_auth_cookies(response, user)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    enforce_csrf(request)
    email = str(request.data.get("email") or "").strip().lower()
    password = str(request.data.get("password") or "")
    user = authenticate(request, username=email, password=password)
    if not user:
        return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)
    membership = active_membership(user)
    if not membership:
        return Response({"detail": "This account does not belong to a ForgeGov workspace."}, status=status.HTTP_403_FORBIDDEN)
    response = Response({
        "user": UserSerializer(user).data,
        "organization": {"id": membership.organization_id, "name": membership.organization.name, "slug": membership.organization.slug},
        "role": membership.role,
    })
    audit(request, "auth.login", membership.organization, "user", user.id)
    return _set_auth_cookies(response, user)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    enforce_csrf(request)
    raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not raw:
        return Response({"detail": "Refresh token is missing."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        refresh_token = RefreshToken(raw)
        user = User.objects.get(pk=refresh_token["user_id"], is_active=True)
    except (TokenError, User.DoesNotExist, KeyError):
        response = Response({"detail": "Refresh token is invalid or expired."}, status=status.HTTP_401_UNAUTHORIZED)
        return _clear_auth_cookies(response)
    try:
        refresh_token.blacklist()
    except Exception:
        pass
    return _set_auth_cookies(Response({"refreshed": True}), user)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    enforce_csrf(request)
    raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if raw:
        try:
            RefreshToken(raw).blacklist()
        except Exception:
            pass
    response = Response({"signed_out": True})
    return _clear_auth_cookies(response)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    membership = active_membership(request.user)
    if not membership:
        return Response({"detail": "No workspace membership found."}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "PATCH":
        for field in ("first_name", "last_name"):
            if field in request.data:
                setattr(request.user, field, str(request.data[field]).strip())
        request.user.save(update_fields=["first_name", "last_name"])
        audit(request, "account.profile_updated", membership.organization, "user", request.user.id)
    return Response({
        "user": UserSerializer(request.user).data,
        "organization": {"id": membership.organization_id, "name": membership.organization.name, "slug": membership.organization.slug},
        "role": membership.role,
    })


@api_view(["GET", "POST"])
@permission_classes([IsOrganizationAdmin])
def invitations(request):
    membership = active_membership(request.user)
    organization = membership.organization
    if request.method == "GET":
        rows = Invitation.objects.filter(organization=organization)
        return Response(InvitationSerializer(rows, many=True).data)

    email = str(request.data.get("email") or "").strip().lower()
    role = str(request.data.get("role") or Membership.Role.VIEWER)
    valid_roles = {value for value, _ in Membership.Role.choices if value != Membership.Role.OWNER}
    if not email or role not in valid_roles:
        return Response({"detail": "A valid email and role are required."}, status=status.HTTP_400_BAD_REQUEST)
    if Membership.objects.filter(organization=organization, user__email__iexact=email).exists():
        return Response({"detail": "This user is already a member."}, status=status.HTTP_400_BAD_REQUEST)
    # Delete older pending tokens so re-inviting the same address cannot violate the status uniqueness constraint.
    Invitation.objects.filter(organization=organization, email__iexact=email, status=Invitation.Status.PENDING).delete()
    record = Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        token=secrets.token_urlsafe(48),
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/register?invite={record.token}"
    audit(request, "team.invitation_created", organization, "invitation", record.id, {"email": email, "role": role})
    data = InvitationSerializer(record).data
    data["invite_url"] = invite_url
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsOrganizationAdmin])
def team_members(request):
    membership = active_membership(request.user)
    rows = Membership.objects.filter(organization=membership.organization).select_related("user", "organization")
    return Response(MembershipSerializer(rows, many=True).data)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsOrganizationAdmin])
def team_member_detail(request, membership_id):
    current = active_membership(request.user)
    target = Membership.objects.filter(pk=membership_id, organization=current.organization).select_related("user").first()
    if not target:
        return Response({"detail": "Team member not found."}, status=status.HTTP_404_NOT_FOUND)
    if target.role == Membership.Role.OWNER:
        return Response({"detail": "Workspace ownership cannot be changed from the team member endpoint."}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == "DELETE":
        if target.user_id == request.user.id:
            return Response({"detail": "You cannot remove your own active membership."}, status=status.HTTP_400_BAD_REQUEST)
        target.delete()
        audit(request, "team.member_removed", current.organization, "membership", membership_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    role = str(request.data.get("role") or "")
    valid_roles = {value for value, _ in Membership.Role.choices if value != Membership.Role.OWNER}
    if role not in valid_roles:
        return Response({"detail": "A valid non-owner role is required."}, status=status.HTTP_400_BAD_REQUEST)
    target.role = role
    target.save(update_fields=["role", "updated_at"])
    audit(request, "team.member_role_updated", current.organization, "membership", membership_id, {"role": role})
    return Response(MembershipSerializer(target).data)


@api_view(["GET"])
@permission_classes([IsOrganizationAdmin])
def audit_logs(request):
    membership = active_membership(request.user)
    rows = AuditLog.objects.filter(organization=membership.organization).select_related("actor")[:250]
    return Response(AuditLogSerializer(rows, many=True).data)
