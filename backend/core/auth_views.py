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
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .authentication import enforce_csrf
from .identity import (
    consume_action_token,
    email_domain,
    finalize_email_verification,
    is_public_email_domain,
    normalize_email,
    organization_for_domain,
    security_profile,
    send_password_reset_email,
    send_verification_email,
)
from .registration_control import effective_registration_mode
from .models import (
    AccountActionToken,
    AuthSession,
    AuditLog,
    CollaborationNotification,
    Invitation,
    Membership,
    Organization,
    OrganizationJoinRequest,
    OrganizationSecurityPolicy,
    PasskeyCredential,
    RecoveryCode,
    SecurityChallenge,
    TOTPDevice,
    UserSecurityProfile,
)
from .permissions import IsOrganizationAdmin, active_membership
from .serializers import AuditLogSerializer, InvitationSerializer, MembershipSerializer, UserSerializer
from .throttles import LoginThrottle, RegistrationThrottle
from .tenant_security import membership_capabilities
from .notifications import create_notification, notify_organization_members, send_system_email
from .security_services import (
    begin_passkey_auth,
    begin_passkey_registration,
    begin_totp_setup,
    confirm_totp,
    consume_security_challenge,
    create_auth_session,
    create_security_challenge,
    disable_totp,
    generate_recovery_codes,
    get_security_challenge,
    mark_step_up,
    mfa_methods,
    org_security_policy,
    passkey_enabled,
    recent_step_up,
    revoke_session,
    session_from_token,
    totp_enabled,
    user_has_mfa,
    verify_passkey_auth,
    verify_passkey_registration,
    verify_recovery_code,
    verify_totp,
)

User = get_user_model()


def _cookie_settings():
    secure = not settings.DEBUG
    return {
        "httponly": True,
        "secure": secure,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }


def _set_auth_cookies(response, user, request=None, refresh_token=None, auth_session=None, organization=None):
    refresh_token = refresh_token or RefreshToken.for_user(user)
    if auth_session is None and request is not None:
        if organization is None:
            membership = active_membership(user)
            organization = membership.organization if membership else None
        auth_session = create_auth_session(user=user, organization=organization, request=request)
    if auth_session is not None:
        refresh_token["fgsid"] = str(auth_session.session_id)
        auth_session.refresh_jti = str(refresh_token.get("jti") or "")
        auth_session.last_seen_at = timezone.now()
        auth_session.save(update_fields=["refresh_jti", "last_seen_at", "updated_at"])
    access = str(refresh_token.access_token)
    cookie = _cookie_settings()
    response.set_cookie(settings.AUTH_ACCESS_COOKIE_NAME, access, max_age=settings.AUTH_ACCESS_COOKIE_MAX_AGE, **cookie)
    response.set_cookie(settings.AUTH_REFRESH_COOKIE_NAME, str(refresh_token), max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE, **cookie)
    return response


def _clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    return response


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def _masked_identifier(email: str) -> str:
    value = normalize_email(email)
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    return f"{local[:2]}***@{domain}"


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


@api_view(["GET"])
@permission_classes([AllowAny])
def registration_config(request):
    mode = effective_registration_mode()
    return Response({
        "mode": mode,
        "public_registration": mode == "public",
        "business_email_required": settings.BUSINESS_EMAIL_REQUIRED,
        "terms_version": settings.TERMS_VERSION,
        "privacy_version": settings.PRIVACY_VERSION,
        "password_min_length": 15,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    enforce_csrf(request)
    email = normalize_email(request.data.get("email"))
    password = str(request.data.get("password") or "")
    first_name = str(request.data.get("first_name") or "").strip()
    last_name = str(request.data.get("last_name") or "").strip()
    organization_name = str(request.data.get("organization_name") or "").strip()
    invitation_token = str(request.data.get("invitation_token") or "").strip()
    accepted_terms = bool(request.data.get("accept_terms"))
    accepted_privacy = bool(request.data.get("accept_privacy"))
    registration_mode = effective_registration_mode()

    if not first_name or not last_name or not email or not password:
        return Response({"detail": "Full name, email, and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    if not accepted_terms or not accepted_privacy:
        return Response({"detail": "You must accept the ForgeGov Terms of Use and Privacy Policy."}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email__iexact=email).exists():
        return Response({"detail": "An account already exists for this email."}, status=status.HTTP_400_BAD_REQUEST)

    domain = email_domain(email)
    if settings.BUSINESS_EMAIL_REQUIRED and is_public_email_domain(domain) and not invitation_token:
        return Response({"detail": "Use a business email address or register through a company invitation."}, status=status.HTTP_400_BAD_REQUEST)

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

        if not invitation and registration_mode in {"private_beta", "invite_only", "closed"}:
            return Response({
                "detail": "ForgeGov registration is currently controlled. A valid company invitation is required.",
                "registration_mode": registration_mode,
            }, status=status.HTTP_403_FORBIDDEN)

        existing_organization = None if invitation else organization_for_domain(domain)
        if not invitation and not existing_organization:
            if not organization_name:
                organization_name = f"{first_name}'s Workspace"
            if Organization.objects.filter(name__iexact=organization_name).exists():
                return Response(
                    {"detail": "That company already has a ForgeGov workspace. Use your company email to request access."},
                    status=status.HTTP_409_CONFLICT,
                )

        now = timezone.now()
        # A valid email-bound invitation proves possession of the mailbox, while
        # public self-registration still requires a separate email verification.
        email_verified_by_invite = bool(invitation)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=email_verified_by_invite,
        )
        security = UserSecurityProfile.objects.create(
            user=user,
            lifecycle_status=(
                UserSecurityProfile.LifecycleStatus.ACTIVE
                if email_verified_by_invite
                else UserSecurityProfile.LifecycleStatus.PENDING_EMAIL
            ),
            account_status=UserSecurityProfile.AccountStatus.ACTIVE,
            email_verified_at=now if email_verified_by_invite else None,
            terms_accepted_at=now,
            terms_version=settings.TERMS_VERSION,
            privacy_accepted_at=now,
            privacy_version=settings.PRIVACY_VERSION,
            registration_email_domain=domain,
            pending_organization=None,
            last_password_change_at=now,
        )

        organization = None
        role = None
        pending_organization = None

        if invitation:
            organization = invitation.organization
            role = invitation.role
            invitation.status = Invitation.Status.ACCEPTED
            invitation.accepted_by = user
            invitation.responded_at = now
            invitation.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])
            Membership.objects.create(
                organization=organization,
                user=user,
                role=role,
                job_title=invitation.job_title,
                department=invitation.department,
            )
        else:
            if existing_organization:
                pending_organization = existing_organization
                security.pending_organization = existing_organization
                security.save(update_fields=["pending_organization", "updated_at"])
            else:
                base_slug = slugify(organization_name) or "workspace"
                slug = base_slug
                suffix = 2
                while Organization.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{suffix}"
                    suffix += 1
                organization = Organization.objects.create(
                    name=organization_name,
                    slug=slug,
                    business_domain=None if is_public_email_domain(domain) else domain or None,
                    status=Organization.Status.TRIAL,
                )
                role = Membership.Role.OWNER
                Membership.objects.create(organization=organization, user=user, role=role)

    audit(
        request,
        "security.registration_created",
        organization or pending_organization,
        "user",
        user.id,
        {
            "identifier": _masked_identifier(email),
            "registration_mode": registration_mode,
            "invitation": bool(invitation),
            "pending_organization": pending_organization.id if pending_organization else None,
            "terms_version": settings.TERMS_VERSION,
            "privacy_version": settings.PRIVACY_VERSION,
        },
    )

    if invitation:
        create_notification(
            organization=organization,
            user=user,
            title="Welcome to ForgeGov",
            message=f"You joined {organization.name}.",
            kind="membership",
            link="/company",
        )
        policy = org_security_policy(organization)
        privileged_mfa = policy.require_mfa_for_financial_roles and role in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.PRICING}
        if policy.require_mfa or privileged_mfa:
            audit(request, "security.invited_user_requires_mfa_enrollment", organization, "user", user.id)
            return Response({
                "user": UserSerializer(user).data,
                "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
                "role": role,
                "email_verified": True,
                "next_step": "sign_in_for_mfa",
            }, status=status.HTTP_201_CREATED)
        response = Response({
            "user": UserSerializer(user).data,
            "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
            "role": role,
            "email_verified": True,
            "next_step": "workspace",
        }, status=status.HTTP_201_CREATED)
        return _set_auth_cookies(response, user, request=request, organization=organization)

    delivered = send_verification_email(user=user, request_ip=_client_ip(request))
    return Response({
        "email": email,
        "email_verified": False,
        "verification_email_sent": delivered,
        "next_step": "verify_email",
        "pending_organization": (
            {"id": pending_organization.id, "name": pending_organization.name}
            if pending_organization else None
        ),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def resend_verification(request):
    enforce_csrf(request)
    email = normalize_email(request.data.get("email"))
    user = User.objects.filter(email__iexact=email).first()
    # Generic response prevents account enumeration.
    if user:
        profile = security_profile(user)
        if not profile.email_verified_at:
            delivered = send_verification_email(user=user, request_ip=_client_ip(request))
            audit(request, "security.email_verification_resent", None, "user", user.id, {"identifier": _masked_identifier(email), "delivered": delivered})
    return Response({"detail": "If the account is eligible, a verification email has been sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email(request):
    enforce_csrf(request)
    raw_token = str(request.data.get("token") or "").strip()
    row = consume_action_token(raw_token, AccountActionToken.Purpose.EMAIL_VERIFICATION)
    if not row:
        return Response({"detail": "This verification link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    profile, next_step = finalize_email_verification(row.user)
    membership = active_membership(row.user)
    organization = membership.organization if membership else None
    audit(request, "security.email_verified", organization, "user", row.user.id, {"next_step": next_step})
    return Response({
        "verified": True,
        "next_step": next_step,
        "organization": (
            {"id": organization.id, "name": organization.name, "slug": organization.slug}
            if organization else None
        ),
        "lifecycle_status": profile.lifecycle_status,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def password_reset_request(request):
    enforce_csrf(request)
    email = normalize_email(request.data.get("email"))
    user = User.objects.filter(email__iexact=email).first()
    if user:
        profile = security_profile(user, legacy_verified=True)
        if profile.email_verified_at and profile.account_status == UserSecurityProfile.AccountStatus.ACTIVE:
            delivered = send_password_reset_email(user=user, request_ip=_client_ip(request))
            audit(request, "security.password_reset_requested", None, "user", user.id, {"identifier": _masked_identifier(email), "delivered": delivered})
    return Response({"detail": "If an eligible ForgeGov account exists, password reset instructions have been sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def password_reset_confirm(request):
    enforce_csrf(request)
    raw_token = str(request.data.get("token") or "").strip()
    new_password = str(request.data.get("password") or "")
    row = AccountActionToken.objects.select_related("user").filter(
        token_hash=__import__("hashlib").sha256(raw_token.encode("utf-8")).hexdigest(),
        purpose=AccountActionToken.Purpose.PASSWORD_RESET,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not row:
        return Response({"detail": "This password reset link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(new_password, user=row.user)
    except ValidationError as exc:
        return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
    now = timezone.now()
    row.user.set_password(new_password)
    row.user.save(update_fields=["password"])
    row.used_at = now
    row.save(update_fields=["used_at", "updated_at"])
    profile = security_profile(row.user, legacy_verified=True)
    profile.last_password_change_at = now
    profile.save(update_fields=["last_password_change_at", "updated_at"])
    # Invalidate outstanding refresh tokens where possible.
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        for token in OutstandingToken.objects.filter(user=row.user):
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:
        pass
    audit(request, "security.password_changed_via_reset", None, "user", row.user.id)
    return Response({"reset": True, "detail": "Password changed. Sign in with your new password."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    enforce_csrf(request)
    email = normalize_email(request.data.get("email"))
    password = str(request.data.get("password") or "")
    user = authenticate(request, username=email, password=password)

    if not user:
        candidate = User.objects.filter(email__iexact=email).first()
        if candidate and candidate.check_password(password):
            profile = security_profile(candidate, legacy_verified=False)
            if not profile.email_verified_at:
                audit(request, "security.login_blocked_unverified", None, "user", candidate.id, {"identifier": _masked_identifier(email)})
                return Response({"detail": "Verify your email before signing in.", "code": "email_unverified"}, status=status.HTTP_403_FORBIDDEN)
            if profile.account_status != UserSecurityProfile.AccountStatus.ACTIVE:
                audit(request, "security.login_blocked_account_state", None, "user", candidate.id, {"state": profile.account_status})
                return Response({"detail": "This account is not available. Contact your ForgeGov administrator.", "code": "account_unavailable"}, status=status.HTTP_403_FORBIDDEN)
        audit(request, "security.login_failed", None, "user", "", {"identifier": _masked_identifier(email)})
        return Response({"detail": "Email or password is incorrect."}, status=status.HTTP_401_UNAUTHORIZED)

    profile = security_profile(user, legacy_verified=True)
    if profile.account_status != UserSecurityProfile.AccountStatus.ACTIVE:
        audit(request, "security.login_blocked_account_state", None, "user", user.id, {"state": profile.account_status})
        return Response({"detail": "This account is not available. Contact your ForgeGov administrator.", "code": "account_unavailable"}, status=status.HTTP_403_FORBIDDEN)

    membership = active_membership(user)
    if not membership:
        pending = OrganizationJoinRequest.objects.filter(user=user, status=OrganizationJoinRequest.Status.PENDING).select_related("organization").first()
        if pending:
            return Response({
                "detail": f"Your request to join {pending.organization.name} is awaiting company approval.",
                "code": "organization_pending",
            }, status=status.HTTP_403_FORBIDDEN)
        return Response({"detail": "This account does not belong to an active ForgeGov workspace.", "code": "no_workspace"}, status=status.HTTP_403_FORBIDDEN)

    if membership.organization.status in {Organization.Status.SUSPENDED, Organization.Status.CANCELLED}:
        audit(request, "security.login_blocked_organization", membership.organization, "user", user.id, {"state": membership.organization.status})
        return Response({"detail": "This company workspace is not currently available.", "code": "organization_unavailable"}, status=status.HTTP_403_FORBIDDEN)

    policy = org_security_policy(membership.organization)
    methods = mfa_methods(user)
    privileged_mfa = policy.require_mfa_for_financial_roles and membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.PRICING}
    mfa_required = policy.require_mfa or privileged_mfa
    if mfa_required and not methods:
        challenge = create_security_challenge(
            user=user,
            purpose=SecurityChallenge.Purpose.MFA_ENROLLMENT,
            payload={"organization_id": membership.organization_id, "role": membership.role},
            minutes=10,
        )
        audit(request, "security.mfa_enrollment_required", membership.organization, "user", user.id)
        return Response({
            "mfa_enrollment_required": True,
            "challenge_token": challenge,
            "detail": "Your company security policy requires MFA. Enroll an authenticator app to continue.",
        }, status=status.HTTP_202_ACCEPTED)

    if methods:
        challenge = create_security_challenge(
            user=user,
            purpose=SecurityChallenge.Purpose.MFA_LOGIN,
            payload={"organization_id": membership.organization_id, "role": membership.role},
            minutes=5,
        )
        audit(request, "security.mfa_challenge_created", membership.organization, "user", user.id, {"methods": methods})
        return Response({
            "mfa_required": True,
            "challenge_token": challenge,
            "methods": methods,
            "detail": "Complete multi-factor authentication to continue.",
        }, status=status.HTTP_202_ACCEPTED)

    return _complete_login(request, user, membership)


def _complete_login(request, user, membership, *, method="password"):
    profile = security_profile(user, legacy_verified=True)
    profile.last_login_ip = _client_ip(request)
    profile.lifecycle_status = UserSecurityProfile.LifecycleStatus.ACTIVE
    profile.save(update_fields=["last_login_ip", "lifecycle_status", "updated_at"])
    auth_session = create_auth_session(user=user, organization=membership.organization, request=request)
    response = Response({
        "user": UserSerializer(user).data,
        "organization": {
            "id": membership.organization_id,
            "name": membership.organization.name,
            "slug": membership.organization.slug,
            "status": membership.organization.status,
        },
        "role": membership.role,
        "mfa_method": method,
    })
    audit(request, "security.login_success", membership.organization, "user", user.id, {"method": method, "session_id": str(auth_session.session_id)})
    return _set_auth_cookies(response, user, request=request, auth_session=auth_session, organization=membership.organization)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def mfa_enrollment_totp_setup(request):
    enforce_csrf(request)
    raw = str(request.data.get("challenge_token") or "")
    challenge = get_security_challenge(raw, SecurityChallenge.Purpose.MFA_ENROLLMENT)
    if not challenge:
        return Response({"detail": "MFA enrollment challenge is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    if totp_enabled(challenge.user):
        return Response({"detail": "An authenticator app is already configured."}, status=status.HTTP_409_CONFLICT)
    result = begin_totp_setup(challenge.user)
    return Response(result)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def mfa_enrollment_totp_confirm(request):
    enforce_csrf(request)
    raw = str(request.data.get("challenge_token") or "")
    challenge = get_security_challenge(raw, SecurityChallenge.Purpose.MFA_ENROLLMENT)
    if not challenge:
        return Response({"detail": "MFA enrollment challenge is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    ok, codes = confirm_totp(challenge.user, str(request.data.get("code") or ""))
    if not ok:
        return Response({"detail": "Authenticator code is invalid."}, status=status.HTTP_400_BAD_REQUEST)
    consume_security_challenge(challenge)
    membership = active_membership(challenge.user)
    if not membership:
        return Response({"detail": "Workspace access is unavailable."}, status=status.HTTP_403_FORBIDDEN)
    audit(request, "security.mfa_enabled", membership.organization, "user", challenge.user_id, {"method": "totp", "enrollment": True})
    _security_notice(challenge.user, membership.organization, "ForgeGov MFA enabled", "An authenticator app was enrolled to satisfy your company security policy.")
    response = _complete_login(request, challenge.user, membership, method="totp_enrollment")
    response.data["recovery_codes"] = codes
    response.data["recovery_detail"] = "Save these recovery codes now. They are shown only once."
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def mfa_verify(request):
    enforce_csrf(request)
    raw = str(request.data.get("challenge_token") or "")
    method = str(request.data.get("method") or "totp")
    code = str(request.data.get("code") or "")
    challenge = get_security_challenge(raw, SecurityChallenge.Purpose.MFA_LOGIN)
    if not challenge:
        return Response({"detail": "MFA challenge is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    user = challenge.user
    ok = verify_totp(user, code) if method == "totp" else verify_recovery_code(user, code) if method == "recovery_code" else False
    if not ok:
        audit(request, "security.mfa_failed", None, "user", user.id, {"method": method})
        return Response({"detail": "The authentication code is invalid."}, status=status.HTTP_400_BAD_REQUEST)
    consume_security_challenge(challenge)
    membership = active_membership(user)
    if not membership:
        return Response({"detail": "Workspace access is unavailable."}, status=status.HTTP_403_FORBIDDEN)
    audit(request, "security.mfa_succeeded", membership.organization, "user", user.id, {"method": method})
    return _complete_login(request, user, membership, method=method)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def mfa_passkey_options(request):
    enforce_csrf(request)
    preauth = str(request.data.get("challenge_token") or "")
    challenge = get_security_challenge(preauth, SecurityChallenge.Purpose.MFA_LOGIN)
    if not challenge or "passkey" not in mfa_methods(challenge.user):
        return Response({"detail": "Passkey authentication is unavailable for this challenge."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        token, options = begin_passkey_auth(challenge.user, preauth_token=preauth)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"challenge_token": token, "options": options})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def mfa_passkey_verify(request):
    enforce_csrf(request)
    webauthn_token = str(request.data.get("challenge_token") or "")
    webauthn_challenge = get_security_challenge(webauthn_token, SecurityChallenge.Purpose.WEBAUTHN_AUTH)
    if not webauthn_challenge:
        return Response({"detail": "Passkey challenge is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    preauth = str(webauthn_challenge.payload.get("preauth_token") or "")
    login_challenge = get_security_challenge(preauth, SecurityChallenge.Purpose.MFA_LOGIN)
    if not login_challenge or login_challenge.user_id != webauthn_challenge.user_id:
        return Response({"detail": "Login challenge is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        ok = verify_passkey_auth(user=webauthn_challenge.user, challenge_token=webauthn_token, credential=request.data.get("credential") or {})
    except Exception:
        ok = False
    if not ok:
        audit(request, "security.mfa_failed", None, "user", webauthn_challenge.user_id, {"method": "passkey"})
        return Response({"detail": "Passkey authentication failed."}, status=status.HTTP_400_BAD_REQUEST)
    consume_security_challenge(login_challenge)
    membership = active_membership(webauthn_challenge.user)
    if not membership:
        return Response({"detail": "Workspace access is unavailable."}, status=status.HTTP_403_FORBIDDEN)
    audit(request, "security.mfa_succeeded", membership.organization, "user", webauthn_challenge.user_id, {"method": "passkey"})
    return _complete_login(request, webauthn_challenge.user, membership, method="passkey")


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
        profile = security_profile(user, legacy_verified=True)
        if profile.account_status != UserSecurityProfile.AccountStatus.ACTIVE:
            raise User.DoesNotExist
        auth_session = session_from_token(refresh_token, user=user)
        if refresh_token.get("fgsid") and not auth_session:
            raise User.DoesNotExist
    except (TokenError, User.DoesNotExist, KeyError):
        response = Response({"detail": "Refresh token is invalid, expired, or revoked."}, status=status.HTTP_401_UNAUTHORIZED)
        return _clear_auth_cookies(response)
    try:
        refresh_token.blacklist()
    except Exception:
        pass
    if auth_session:
        auth_session.last_seen_at = timezone.now()
        auth_session.save(update_fields=["last_seen_at", "updated_at"])
    return _set_auth_cookies(Response({"refreshed": True}), user, request=request, auth_session=auth_session)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    enforce_csrf(request)
    raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    organization = active_membership(user).organization if user and active_membership(user) else None
    if raw:
        try:
            token = RefreshToken(raw)
            session = session_from_token(token, user=user) if user else None
            if session:
                revoke_session(session)
            token.blacklist()
        except Exception:
            pass
    if user:
        audit(request, "security.logout", organization, "user", user.id)
    response = Response({"signed_out": True})
    return _clear_auth_cookies(response)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def security_overview(request):
    profile = security_profile(request.user, legacy_verified=True)
    membership = active_membership(request.user)
    policy = org_security_policy(membership.organization) if membership else None
    current_session = session_from_token(request.auth, user=request.user)
    sessions = AuthSession.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).order_by("-last_seen_at")[:20]
    passkeys = PasskeyCredential.objects.filter(user=request.user, active=True)
    security_events = AuditLog.objects.filter(actor=request.user, action__startswith="security.").order_by("-created_at")[:20]
    return Response({
        "email": request.user.email,
        "email_verified": bool(profile.email_verified_at),
        "email_verified_at": profile.email_verified_at,
        "lifecycle_status": profile.lifecycle_status,
        "account_status": profile.account_status,
        "terms": {"accepted_at": profile.terms_accepted_at, "version": profile.terms_version},
        "privacy": {"accepted_at": profile.privacy_accepted_at, "version": profile.privacy_version},
        "last_password_change_at": profile.last_password_change_at,
        "last_login_ip": profile.last_login_ip,
        "organization_status": membership.organization.status if membership else None,
        "registration_mode": effective_registration_mode(),
        "mfa": {
            "available": True,
            "enabled": user_has_mfa(request.user),
            "totp_enabled": totp_enabled(request.user),
            "passkey_enabled": passkey_enabled(request.user),
            "methods": mfa_methods(request.user),
            "recovery_codes_remaining": RecoveryCode.objects.filter(user=request.user, used_at__isnull=True).count(),
            "required_by_organization": bool(policy and policy.require_mfa),
        },
        "organization_security": {
            "require_mfa": bool(policy and policy.require_mfa),
            "require_mfa_for_financial_roles": bool(policy and policy.require_mfa_for_financial_roles),
            "require_mfa_for_exports": bool(policy and policy.require_mfa_for_exports),
            "require_mfa_for_project_room_admin": bool(policy and policy.require_mfa_for_project_room_admin),
            "session_max_days": policy.session_max_days if policy else 7,
            "can_manage": bool(membership and membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}),
        },
        "sessions": [{
            "session_id": str(row.session_id),
            "device_label": row.device_label,
            "ip_address": row.ip_address,
            "created_at": row.created_at,
            "last_seen_at": row.last_seen_at,
            "expires_at": row.expires_at,
            "current": bool(current_session and row.session_id == current_session.session_id),
            "step_up_at": row.step_up_at,
        } for row in sessions],
        "passkeys": [{
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "last_used_at": row.last_used_at,
            "device_type": row.device_type,
            "backed_up": row.backed_up,
        } for row in passkeys],
        "recent_activity": [{
            "id": row.id,
            "action": row.action,
            "created_at": row.created_at,
            "ip_address": row.ip_address,
            "metadata": row.metadata,
        } for row in security_events],
    })


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
        "organization": {
            "id": membership.organization_id,
            "name": membership.organization.name,
            "slug": membership.organization.slug,
            "status": membership.organization.status,
        },
        "role": membership.role,
        "capabilities": membership_capabilities(membership),
    })



def _current_auth_session(request):
    return session_from_token(request.auth, user=request.user)


def _require_step_up(request):
    row = _current_auth_session(request)
    if not recent_step_up(row):
        raise PermissionDenied("Recent authentication is required for this security change.")
    return row


def _security_notice(user, organization, title, message):
    create_notification(organization=organization, user=user, title=title, message=message, kind="security", link="/security")
    try:
        send_system_email(subject=title, message=message, recipient=user.email, html_message=f"<p>{message}</p>")
    except Exception:
        pass


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def step_up_authentication(request):
    enforce_csrf(request)
    password = str(request.data.get("password") or "")
    method = str(request.data.get("method") or "")
    code = str(request.data.get("code") or "")
    if not request.user.check_password(password):
        audit(request, "security.step_up_failed", active_membership(request.user).organization if active_membership(request.user) else None, "user", request.user.id, {"reason": "password"})
        return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
    if totp_enabled(request.user):
        ok = verify_totp(request.user, code) if method == "totp" else verify_recovery_code(request.user, code) if method == "recovery_code" else False
        if not ok:
            audit(request, "security.step_up_failed", active_membership(request.user).organization if active_membership(request.user) else None, "user", request.user.id, {"reason": "mfa", "method": method})
            return Response({"detail": "A valid authenticator or recovery code is required."}, status=status.HTTP_400_BAD_REQUEST)
    row = _current_auth_session(request)
    if not row:
        return Response({"detail": "Sign in again before changing security settings."}, status=status.HTTP_409_CONFLICT)
    mark_step_up(row)
    membership = active_membership(request.user)
    audit(request, "security.step_up_succeeded", membership.organization if membership else None, "user", request.user.id, {"method": method or "password"})
    return Response({"step_up": True, "valid_for_minutes": 10})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_setup(request):
    enforce_csrf(request)
    password = str(request.data.get("password") or "")
    if not request.user.check_password(password):
        return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
    if totp_enabled(request.user):
        return Response({"detail": "An authenticator app is already configured."}, status=status.HTTP_409_CONFLICT)
    result = begin_totp_setup(request.user)
    membership = active_membership(request.user)
    audit(request, "security.totp_setup_started", membership.organization if membership else None, "user", request.user.id)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_confirm(request):
    enforce_csrf(request)
    ok, codes = confirm_totp(request.user, str(request.data.get("code") or ""))
    if not ok:
        return Response({"detail": "Authenticator code is invalid."}, status=status.HTTP_400_BAD_REQUEST)
    membership = active_membership(request.user)
    organization = membership.organization if membership else None
    audit(request, "security.mfa_enabled", organization, "user", request.user.id, {"method": "totp"})
    _security_notice(request.user, organization, "ForgeGov MFA enabled", "An authenticator app was enabled for your ForgeGov account.")
    return Response({"enabled": True, "recovery_codes": codes, "detail": "Save these recovery codes now. They are shown only once."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_disable(request):
    enforce_csrf(request)
    _require_step_up(request)
    membership = active_membership(request.user)
    policy = org_security_policy(membership.organization) if membership else None
    if policy and policy.require_mfa and not passkey_enabled(request.user):
        return Response({"detail": "Your company requires MFA. Add a passkey before removing your authenticator app."}, status=status.HTTP_409_CONFLICT)
    disable_totp(request.user)
    organization = membership.organization if membership else None
    audit(request, "security.mfa_disabled", organization, "user", request.user.id, {"method": "totp"})
    _security_notice(request.user, organization, "ForgeGov authenticator removed", "The authenticator app and recovery codes were removed from your ForgeGov account.")
    return Response({"disabled": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recovery_codes_regenerate(request):
    enforce_csrf(request)
    _require_step_up(request)
    if not totp_enabled(request.user):
        return Response({"detail": "Enable an authenticator app before generating recovery codes."}, status=status.HTTP_409_CONFLICT)
    codes = generate_recovery_codes(request.user)
    membership = active_membership(request.user)
    audit(request, "security.recovery_codes_regenerated", membership.organization if membership else None, "user", request.user.id)
    return Response({"recovery_codes": codes, "detail": "Old recovery codes are invalid. Save these codes now; they are shown only once."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def passkey_register_options(request):
    enforce_csrf(request)
    _require_step_up(request)
    token, options = begin_passkey_registration(request.user)
    return Response({"challenge_token": token, "options": options})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def passkey_register_verify(request):
    enforce_csrf(request)
    _require_step_up(request)
    try:
        row = verify_passkey_registration(
            user=request.user,
            challenge_token=str(request.data.get("challenge_token") or ""),
            credential=request.data.get("credential") or {},
            name=str(request.data.get("name") or "Passkey"),
        )
    except Exception as exc:
        return Response({"detail": f"Passkey registration failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
    membership = active_membership(request.user)
    organization = membership.organization if membership else None
    audit(request, "security.passkey_added", organization, "passkey", row.id, {"name": row.name})
    _security_notice(request.user, organization, "ForgeGov passkey added", f"A new passkey named '{row.name}' was added to your ForgeGov account.")
    return Response({"registered": True, "id": row.id, "name": row.name})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def passkey_delete(request, passkey_id):
    enforce_csrf(request)
    _require_step_up(request)
    row = PasskeyCredential.objects.filter(pk=passkey_id, user=request.user, active=True).first()
    if not row:
        return Response({"detail": "Passkey not found."}, status=status.HTTP_404_NOT_FOUND)
    membership = active_membership(request.user)
    policy = org_security_policy(membership.organization) if membership else None
    other_passkey = PasskeyCredential.objects.filter(user=request.user, active=True).exclude(pk=row.pk).exists()
    if policy and policy.require_mfa and not totp_enabled(request.user) and not other_passkey:
        return Response({"detail": "Your company requires MFA. Add another MFA method before removing this passkey."}, status=status.HTTP_409_CONFLICT)
    name = row.name
    row.active = False
    row.save(update_fields=["active", "updated_at"])
    organization = membership.organization if membership else None
    audit(request, "security.passkey_removed", organization, "passkey", row.id, {"name": name})
    _security_notice(request.user, organization, "ForgeGov passkey removed", f"The passkey named '{name}' was removed from your ForgeGov account.")
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def session_revoke(request, session_id):
    enforce_csrf(request)
    row = AuthSession.objects.filter(session_id=session_id, user=request.user, revoked_at__isnull=True).first()
    if not row:
        return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
    current = _current_auth_session(request)
    revoke_session(row)
    membership = active_membership(request.user)
    audit(request, "security.session_revoked", membership.organization if membership else None, "auth_session", row.session_id, {"current": bool(current and current.session_id == row.session_id)})
    response = Response({"revoked": True, "current": bool(current and current.session_id == row.session_id)})
    if current and current.session_id == row.session_id:
        return _clear_auth_cookies(response)
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sessions_revoke_others(request):
    enforce_csrf(request)
    _require_step_up(request)
    current = _current_auth_session(request)
    rows = AuthSession.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now())
    if current:
        rows = rows.exclude(pk=current.pk)
    now = timezone.now()
    count = rows.update(revoked_at=now, updated_at=now)
    membership = active_membership(request.user)
    audit(request, "security.other_sessions_revoked", membership.organization if membership else None, "user", request.user.id, {"count": count})
    return Response({"revoked_sessions": count})


@api_view(["GET", "PATCH"])
@permission_classes([IsOrganizationAdmin])
def organization_security_policy(request):
    enforce_csrf(request) if request.method == "PATCH" else None
    membership = active_membership(request.user)
    policy = org_security_policy(membership.organization)
    if request.method == "PATCH":
        _require_step_up(request)
        desired_require_mfa = bool(request.data.get("require_mfa", policy.require_mfa))
        if desired_require_mfa and not policy.require_mfa:
            members = Membership.objects.filter(organization=membership.organization, active=True).select_related("user")
            missing = [row.user.email for row in members if not user_has_mfa(row.user)]
            if missing:
                return Response({
                    "detail": "MFA cannot be required until every active company member has enrolled at least one MFA method.",
                    "members_without_mfa": missing,
                }, status=status.HTTP_409_CONFLICT)
        policy.require_mfa = desired_require_mfa
        if "require_mfa_for_financial_roles" in request.data:
            policy.require_mfa_for_financial_roles = bool(request.data.get("require_mfa_for_financial_roles"))
        if "require_mfa_for_exports" in request.data:
            policy.require_mfa_for_exports = bool(request.data.get("require_mfa_for_exports"))
        if "require_mfa_for_project_room_admin" in request.data:
            policy.require_mfa_for_project_room_admin = bool(request.data.get("require_mfa_for_project_room_admin"))
        if "session_max_days" in request.data:
            policy.session_max_days = max(1, min(int(request.data.get("session_max_days") or 7), 7))
        policy.updated_by = request.user
        policy.save()
        audit(request, "security.organization_policy_updated", membership.organization, "organization_security_policy", policy.id, {"require_mfa": policy.require_mfa, "session_max_days": policy.session_max_days})
    return Response({
        "require_mfa": policy.require_mfa,
        "require_mfa_for_financial_roles": policy.require_mfa_for_financial_roles,
        "require_mfa_for_exports": policy.require_mfa_for_exports,
        "require_mfa_for_project_room_admin": policy.require_mfa_for_project_room_admin,
        "session_max_days": policy.session_max_days,
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def workspaces(request):
    memberships = Membership.objects.filter(user=request.user, active=True).exclude(
        organization__status__in=[Organization.Status.SUSPENDED, Organization.Status.CANCELLED]
    ).select_related("organization").order_by("organization__name")
    if request.method == "POST":
        membership = memberships.filter(organization_id=request.data.get("organization")).first()
        if not membership:
            return Response({"detail": "You do not have access to that workspace."}, status=status.HTTP_403_FORBIDDEN)
        response = Response({"organization": {"id": membership.organization_id, "name": membership.organization.name, "slug": membership.organization.slug}, "role": membership.role})
        response.set_cookie("forgegov_workspace", str(membership.organization_id), secure=not settings.DEBUG, httponly=False, samesite="Lax", max_age=60*60*24*365)
        return response
    active = active_membership(request.user)
    return Response({"active_organization": active.organization_id if active else None, "workspaces": [{"organization":{"id":m.organization_id,"name":m.organization.name,"slug":m.organization.slug},"role":m.role,"job_title":m.job_title} for m in memberships]})
