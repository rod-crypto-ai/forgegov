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
from .models import AuditLog, CollaborationNotification, Invitation, Membership, Organization
from .permissions import IsOrganizationAdmin, active_membership
from .serializers import AuditLogSerializer, InvitationSerializer, MembershipSerializer, UserSerializer
from .throttles import LoginThrottle, RegistrationThrottle
from .notifications import create_notification, notify_organization_members, send_system_email

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
            invitation.accepted_by = user
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])
        else:
            if not organization_name:
                organization_name = f"{first_name or email.split('@')[0]}'s Workspace"
            if Organization.objects.filter(name__iexact=organization_name).exists():
                return Response({"detail": "That company already has a ForgeGov workspace. Ask its owner for an invitation."}, status=status.HTTP_409_CONFLICT)
            base_slug = slugify(organization_name) or "workspace"
            slug = base_slug
            suffix = 2
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            organization = Organization.objects.create(name=organization_name, slug=slug)
            role = Membership.Role.OWNER
        Membership.objects.create(organization=organization, user=user, role=role, job_title=invitation.job_title if invitation else "", department=invitation.department if invitation else "")

    response = Response({
        "user": UserSerializer(user).data,
        "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        "role": role,
    }, status=status.HTTP_201_CREATED)
    audit(request, "auth.register", organization, "user", user.id, {"email": email})
    create_notification(organization=organization, user=user, title="Welcome to ForgeGov", message=f"You joined {organization.name}.", kind="membership", link="/company")
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
    # Preserve invitation history while ensuring only one pending token remains.
    Invitation.objects.filter(organization=organization, email__iexact=email, status=Invitation.Status.PENDING).update(status=Invitation.Status.CANCELLED, responded_at=timezone.now())
    record = Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        job_title=str(request.data.get("job_title") or "")[:120],
        department=str(request.data.get("department") or "")[:120],
        token=secrets.token_urlsafe(48),
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7),
        last_sent_at=timezone.now(),
    )
    invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/register?invite={record.token}"
    delivered = send_system_email(
        subject=f"You were invited to join {organization.name} on ForgeGov",
        message=f"{request.user.get_full_name() or request.user.email} invited you to join {organization.name}. Accept your invitation: {invite_url}",
        recipient=email,
        html_message=f"<p>You were invited to join <strong>{organization.name}</strong> on ForgeGov.</p><p><a href=\"{invite_url}\">Accept invitation</a></p><p>This invitation expires in 7 days.</p>",
    )
    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user:
        create_notification(organization=organization, user=existing_user, title=f"Invitation to {organization.name}", message="Accept the invitation to join this company workspace.", kind="invitation", link=invite_url)
    audit(request, "team.invitation_created", organization, "invitation", record.id, {"email": email, "role": role, "email_delivered": delivered})
    data = InvitationSerializer(record).data
    data["invite_url"] = invite_url
    data["email_delivered"] = delivered
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsOrganizationAdmin])
def invitation_action(request, invitation_id):
    membership = active_membership(request.user)
    record = Invitation.objects.filter(pk=invitation_id, organization=membership.organization).first()
    if not record:
        return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action == "cancel":
        if record.status != Invitation.Status.PENDING:
            return Response({"detail": "Only pending invitations can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        record.status = Invitation.Status.CANCELLED
        record.responded_at = timezone.now()
        record.save(update_fields=["status", "responded_at", "updated_at"])
        audit(request, "team.invitation_cancelled", membership.organization, "invitation", record.id)
    elif action == "resend":
        if record.status not in {Invitation.Status.PENDING, Invitation.Status.EXPIRED}:
            return Response({"detail": "Only pending or expired invitations can be resent."}, status=status.HTTP_400_BAD_REQUEST)
        record.status = Invitation.Status.PENDING
        record.token = secrets.token_urlsafe(48)
        record.expires_at = timezone.now() + timedelta(days=7)
        record.resend_count += 1
        record.last_sent_at = timezone.now()
        record.save(update_fields=["status", "token", "expires_at", "resend_count", "last_sent_at", "updated_at"])
        invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/register?invite={record.token}"
        delivered = send_system_email(subject=f"Reminder: join {membership.organization.name} on ForgeGov", message=f"Accept your invitation: {invite_url}", recipient=record.email, html_message=f"<p><a href=\"{invite_url}\">Accept invitation</a></p>")
        audit(request, "team.invitation_resent", membership.organization, "invitation", record.id, {"email_delivered": delivered})
    else:
        return Response({"detail": "action must be resend or cancel."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(InvitationSerializer(record).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_invitations(request):
    email = str(request.user.email or "").strip().lower()
    if not email:
        return Response([])
    rows = Invitation.objects.filter(
        email__iexact=email,
        status=Invitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).select_related("organization", "invited_by").order_by("-created_at")
    payload = []
    for row in rows:
        data = InvitationSerializer(row).data
        data["organization_name"] = row.organization.name
        data["invited_by_name"] = (row.invited_by.get_full_name() or row.invited_by.email) if row.invited_by else "ForgeGov administrator"
        payload.append(data)
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pending_invitation_response(request, invitation_id):
    email = str(request.user.email or "").strip().lower()
    row = Invitation.objects.select_related("organization", "invited_by").filter(
        pk=invitation_id,
        email__iexact=email,
        status=Invitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).first()
    if not row:
        return Response({"detail": "Pending invitation not found or expired."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action not in {"accept", "decline"}:
        return Response({"detail": "action must be accept or decline."}, status=status.HTTP_400_BAD_REQUEST)
    if action == "accept":
        existing = Membership.objects.filter(user=request.user, active=True).exclude(organization=row.organization).first()
        if existing:
            return Response({"detail": "This account already belongs to another active company workspace. Ask the inviting company to use a partner-company invitation instead."}, status=status.HTTP_409_CONFLICT)
        membership, _ = Membership.objects.update_or_create(
            organization=row.organization,
            user=request.user,
            defaults={"role": row.role, "job_title": row.job_title, "department": row.department, "active": True},
        )
        row.status = Invitation.Status.ACCEPTED
        row.accepted_by = request.user
        row.responded_at = timezone.now()
        row.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])
        create_notification(organization=row.organization, user=request.user, title=f"You joined {row.organization.name}", message="Your company membership is active.", kind="membership", link="/company")
        notify_organization_members(organization=row.organization, title="Employee invitation accepted", message=f"{request.user.email} joined the company workspace.", kind="invitation_response", link="/company", roles=[Membership.Role.OWNER, Membership.Role.ADMIN])
        audit(request, "team.invitation_accepted", row.organization, "invitation", row.id, {"membership": membership.id})
    else:
        row.status = Invitation.Status.DECLINED
        row.responded_at = timezone.now()
        row.save(update_fields=["status", "responded_at", "updated_at"])
        notify_organization_members(organization=row.organization, title="Employee invitation declined", message=f"{request.user.email} declined the company invitation.", kind="invitation_response", link="/company", roles=[Membership.Role.OWNER, Membership.Role.ADMIN])
        audit(request, "team.invitation_declined", row.organization, "invitation", row.id)
    return Response(InvitationSerializer(row).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def invitation_preview(request):
    token = str(request.query_params.get("token") or "").strip()
    row = Invitation.objects.select_related("organization", "invited_by").filter(
        token=token, status=Invitation.Status.PENDING, expires_at__gt=timezone.now()
    ).first()
    if not row:
        return Response({"detail": "Invitation not found or expired."}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        "email": row.email,
        "organization_name": row.organization.name,
        "role": row.role,
        "job_title": row.job_title,
        "department": row.department,
        "expires_at": row.expires_at,
        "invited_by_name": (row.invited_by.get_full_name() or row.invited_by.email) if row.invited_by else "ForgeGov administrator",
    })


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
    role = str(request.data.get("role") or target.role)
    valid_roles = {value for value, _ in Membership.Role.choices if value != Membership.Role.OWNER}
    if role not in valid_roles:
        return Response({"detail": "A valid non-owner role is required."}, status=status.HTTP_400_BAD_REQUEST)
    target.role = role
    if "job_title" in request.data:
        target.job_title = str(request.data.get("job_title") or "")[:120]
    if "department" in request.data:
        target.department = str(request.data.get("department") or "")[:120]
    if "active" in request.data:
        target.active = bool(request.data.get("active"))
    target.save(update_fields=["role", "job_title", "department", "active", "updated_at"])
    audit(request, "team.member_updated", current.organization, "membership", membership_id, {"role": role, "active": target.active})
    return Response(MembershipSerializer(target).data)


@api_view(["GET"])
@permission_classes([IsOrganizationAdmin])
def audit_logs(request):
    membership = active_membership(request.user)
    rows = AuditLog.objects.filter(organization=membership.organization).select_related("actor")[:250]
    return Response(AuditLogSerializer(rows, many=True).data)
