from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    AccountActionToken,
    Organization,
    OrganizationJoinRequest,
    OrganizationProfile,
    UserSecurityProfile,
)
from .notifications import notify_organization_members, send_system_email

User = get_user_model()


PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "mail.com",
}


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def email_domain(email: str) -> str:
    value = normalize_email(email)
    return value.rsplit("@", 1)[1] if "@" in value else ""


def is_public_email_domain(domain: str) -> bool:
    return str(domain or "").strip().lower() in PUBLIC_EMAIL_DOMAINS


def website_domain(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    return host.removeprefix("www.")


def security_profile(user, *, legacy_verified: bool = False) -> UserSecurityProfile:
    defaults = {}
    if legacy_verified:
        defaults = {
            "lifecycle_status": UserSecurityProfile.LifecycleStatus.ACTIVE,
            "email_verified_at": timezone.now(),
            "last_password_change_at": timezone.now(),
        }
    profile, _ = UserSecurityProfile.objects.get_or_create(user=user, defaults=defaults)
    return profile


def organization_for_domain(domain: str) -> Organization | None:
    domain = str(domain or "").strip().lower()
    if not domain or is_public_email_domain(domain):
        return None
    direct = Organization.objects.filter(business_domain__iexact=domain).first()
    if direct:
        return direct

    # Backfill from an already-verified company website without changing the
    # security rule: domain matching only discovers the company; owners/admins
    # still approve access.
    for profile in OrganizationProfile.objects.select_related("organization").filter(verified=True).exclude(website=""):
        if website_domain(profile.website) == domain:
            organization = profile.organization
            if not organization.business_domain:
                organization.business_domain = domain
                try:
                    organization.save(update_fields=["business_domain", "updated_at"])
                except Exception:
                    pass
            return organization
    return None


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_action_token(*, user, purpose: str, request_ip: str | None = None, lifetime_minutes: int = 30) -> str:
    AccountActionToken.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())

    raw = secrets.token_urlsafe(32)
    AccountActionToken.objects.create(
        user=user,
        purpose=purpose,
        token_hash=_hash_token(raw),
        expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
        requested_ip=request_ip,
    )
    return raw


def consume_action_token(raw_token: str, purpose: str) -> AccountActionToken | None:
    token_hash = _hash_token(str(raw_token or ""))
    row = AccountActionToken.objects.select_related("user").filter(
        token_hash=token_hash,
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not row:
        return None
    row.used_at = timezone.now()
    row.save(update_fields=["used_at", "updated_at"])
    return row


def send_verification_email(*, user, request_ip: str | None = None) -> bool:
    raw = create_action_token(
        user=user,
        purpose=AccountActionToken.Purpose.EMAIL_VERIFICATION,
        request_ip=request_ip,
        lifetime_minutes=settings.EMAIL_VERIFICATION_TOKEN_MINUTES,
    )
    url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={raw}"
    return send_system_email(
        subject="Verify your ForgeGov email",
        message=f"Verify your ForgeGov account: {url}",
        recipient=user.email,
        html_message=(
            "<p>Verify your email to activate your ForgeGov identity.</p>"
            f"<p><a href=\"{url}\">Verify email</a></p>"
            f"<p>This link expires in {settings.EMAIL_VERIFICATION_TOKEN_MINUTES} minutes.</p>"
        ),
    )


def send_password_reset_email(*, user, request_ip: str | None = None) -> bool:
    raw = create_action_token(
        user=user,
        purpose=AccountActionToken.Purpose.PASSWORD_RESET,
        request_ip=request_ip,
        lifetime_minutes=settings.PASSWORD_RESET_TOKEN_MINUTES,
    )
    url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={raw}"
    return send_system_email(
        subject="Reset your ForgeGov password",
        message=f"Reset your ForgeGov password: {url}",
        recipient=user.email,
        html_message=(
            "<p>A password reset was requested for your ForgeGov account.</p>"
            f"<p><a href=\"{url}\">Reset password</a></p>"
            f"<p>This link expires in {settings.PASSWORD_RESET_TOKEN_MINUTES} minutes.</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        ),
    )


def finalize_email_verification(user) -> tuple[UserSecurityProfile, str]:
    profile = security_profile(user)
    now = timezone.now()
    profile.email_verified_at = now

    pending_join = None
    if profile.pending_organization_id:
        pending_join, _ = OrganizationJoinRequest.objects.get_or_create(
            organization=profile.pending_organization,
            user=user,
            status=OrganizationJoinRequest.Status.PENDING,
            defaults={
                "email_domain": profile.registration_email_domain,
                "requested_role": "viewer",
            },
        )

    if pending_join:
        profile.lifecycle_status = UserSecurityProfile.LifecycleStatus.PENDING_ORGANIZATION
        next_step = "pending_organization_approval"
        notify_organization_members(
            organization=pending_join.organization,
            title="Verified company join request",
            message=f"{user.email} verified their email and is requesting access to {pending_join.organization.name}.",
            kind="company_join_request",
            link="/company",
        )
    else:
        profile.lifecycle_status = UserSecurityProfile.LifecycleStatus.ACTIVE
        next_step = "sign_in"

    profile.save(update_fields=["email_verified_at", "lifecycle_status", "updated_at"])
    user.is_active = True
    user.save(update_fields=["is_active"])
    return profile, next_step
