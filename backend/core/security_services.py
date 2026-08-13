from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import urlparse

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import (
    AuthSession,
    OrganizationSecurityPolicy,
    PasskeyCredential,
    RecoveryCode,
    SecurityChallenge,
    TOTPDevice,
)


def _fernet() -> Fernet:
    # Stable application encryption key derived from Django's deployment secret.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored MFA secret cannot be decrypted with the current application key.") from exc


def org_security_policy(organization) -> OrganizationSecurityPolicy:
    policy, _ = OrganizationSecurityPolicy.objects.get_or_create(organization=organization)
    return policy


def user_has_mfa(user) -> bool:
    return TOTPDevice.objects.filter(user=user, active=True, confirmed_at__isnull=False).exists() or PasskeyCredential.objects.filter(user=user, active=True).exists()


def totp_enabled(user) -> bool:
    return TOTPDevice.objects.filter(user=user, active=True, confirmed_at__isnull=False).exists()


def passkey_enabled(user) -> bool:
    return PasskeyCredential.objects.filter(user=user, active=True).exists()


def mfa_methods(user) -> list[str]:
    methods: list[str] = []
    if totp_enabled(user):
        methods.append("totp")
    if RecoveryCode.objects.filter(user=user, used_at__isnull=True).exists():
        methods.append("recovery_code")
    if passkey_enabled(user):
        methods.append("passkey")
    return methods


def generate_recovery_codes(user, count: int = 10) -> list[str]:
    RecoveryCode.objects.filter(user=user).delete()
    raw_codes: list[str] = []
    rows = []
    for _ in range(count):
        code = f"{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"
        raw_codes.append(code)
        rows.append(RecoveryCode(user=user, code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest()))
    RecoveryCode.objects.bulk_create(rows)
    return raw_codes


def verify_recovery_code(user, code: str) -> bool:
    digest = hashlib.sha256(str(code or "").strip().upper().encode("utf-8")).hexdigest()
    row = RecoveryCode.objects.filter(user=user, code_hash=digest, used_at__isnull=True).first()
    if not row:
        return False
    row.used_at = timezone.now()
    row.save(update_fields=["used_at", "updated_at"])
    return True


def begin_totp_setup(user) -> dict:
    secret = pyotp.random_base32()
    device, _ = TOTPDevice.objects.update_or_create(
        user=user,
        defaults={
            "name": "Authenticator app",
            "secret_encrypted": encrypt_secret(secret),
            "confirmed_at": None,
            "active": False,
        },
    )
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email or user.get_username(), issuer_name="ForgeGov")
    return {"secret": secret, "provisioning_uri": uri, "device_id": device.id}


def confirm_totp(user, code: str) -> tuple[bool, list[str]]:
    device = TOTPDevice.objects.filter(user=user).first()
    if not device:
        return False, []
    secret = decrypt_secret(device.secret_encrypted)
    if not pyotp.TOTP(secret).verify(str(code or "").replace(" ", ""), valid_window=1):
        return False, []
    now = timezone.now()
    device.active = True
    device.confirmed_at = now
    device.last_used_at = now
    device.save(update_fields=["active", "confirmed_at", "last_used_at", "updated_at"])
    return True, generate_recovery_codes(user)


def verify_totp(user, code: str) -> bool:
    device = TOTPDevice.objects.filter(user=user, active=True, confirmed_at__isnull=False).first()
    if not device:
        return False
    if not pyotp.TOTP(decrypt_secret(device.secret_encrypted)).verify(str(code or "").replace(" ", ""), valid_window=1):
        return False
    device.last_used_at = timezone.now()
    device.save(update_fields=["last_used_at", "updated_at"])
    return True


def disable_totp(user) -> None:
    TOTPDevice.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_security_challenge(*, user, purpose: str, challenge: str = "", payload: dict | None = None, minutes: int = 5) -> str:
    raw = secrets.token_urlsafe(32)
    SecurityChallenge.objects.create(
        user=user,
        purpose=purpose,
        token_hash=_hash_token(raw),
        challenge=challenge,
        payload=payload or {},
        expires_at=timezone.now() + timedelta(minutes=minutes),
    )
    return raw


def get_security_challenge(raw: str, purpose: str, *, consume: bool = False):
    row = SecurityChallenge.objects.select_related("user").filter(
        token_hash=_hash_token(str(raw or "")),
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if row and consume:
        row.used_at = timezone.now()
        row.save(update_fields=["used_at", "updated_at"])
    return row


def consume_security_challenge(row) -> None:
    if row.used_at is None:
        row.used_at = timezone.now()
        row.save(update_fields=["used_at", "updated_at"])


def describe_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    browser = "Browser"
    if "edg/" in ua:
        browser = "Microsoft Edge"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "firefox/" in ua:
        browser = "Firefox"
    platform = "device"
    if "iphone" in ua:
        platform = "iPhone"
    elif "ipad" in ua:
        platform = "iPad"
    elif "macintosh" in ua or "mac os" in ua:
        platform = "Mac"
    elif "windows" in ua:
        platform = "Windows PC"
    elif "android" in ua:
        platform = "Android"
    return f"{browser} on {platform}"


def create_auth_session(*, user, organization, request, max_days: int | None = None) -> AuthSession:
    policy = org_security_policy(organization) if organization else None
    days = max_days or (policy.session_max_days if policy else 7)
    return AuthSession.objects.create(
        user=user,
        organization=organization,
        ip_address=_client_ip(request),
        user_agent=str(request.META.get("HTTP_USER_AGENT") or "")[:2000],
        device_label=describe_device(str(request.META.get("HTTP_USER_AGENT") or "")),
        expires_at=timezone.now() + timedelta(days=max(1, min(int(days), 7))),
        last_seen_at=timezone.now(),
    )


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def revoke_session(row: AuthSession) -> None:
    if not row.revoked_at:
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at", "updated_at"])


def session_from_token(token, user=None) -> AuthSession | None:
    sid = token.get("fgsid") if token is not None else None
    if not sid:
        return None
    qs = AuthSession.objects.filter(session_id=sid, revoked_at__isnull=True, expires_at__gt=timezone.now())
    if user is not None:
        qs = qs.filter(user=user)
    return qs.first()


def mark_step_up(row: AuthSession) -> None:
    row.step_up_at = timezone.now()
    row.save(update_fields=["step_up_at", "updated_at"])


def recent_step_up(row: AuthSession | None, minutes: int | None = None) -> bool:
    window = minutes if minutes is not None else int(getattr(settings, "MFA_STEP_UP_MINUTES", 10))
    return bool(row and row.step_up_at and row.step_up_at >= timezone.now() - timedelta(minutes=window))


def webauthn_config() -> tuple[str, str]:
    origin = getattr(settings, "WEBAUTHN_ORIGIN", "") or getattr(settings, "FRONTEND_URL", "")
    parsed = urlparse(origin)
    rp_id = getattr(settings, "WEBAUTHN_RP_ID", "") or (parsed.hostname or "localhost")
    expected_origin = getattr(settings, "WEBAUTHN_ORIGIN", "") or f"{parsed.scheme or 'https'}://{parsed.netloc or rp_id}"
    return rp_id, expected_origin.rstrip("/")


def begin_passkey_registration(user) -> tuple[str, dict]:
    rp_id, _ = webauthn_config()
    existing = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(row.credential_id))
        for row in PasskeyCredential.objects.filter(user=user, active=True)
    ]
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name="ForgeGov",
        user_id=str(user.pk).encode("utf-8"),
        user_name=user.email or user.get_username(),
        user_display_name=user.get_full_name() or user.email or user.get_username(),
        exclude_credentials=existing,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    challenge_b64 = bytes_to_base64url(options.challenge)
    raw = create_security_challenge(
        user=user,
        purpose=SecurityChallenge.Purpose.WEBAUTHN_REGISTER,
        challenge=challenge_b64,
        minutes=5,
    )
    return raw, json.loads(options_to_json(options))


def verify_passkey_registration(*, user, challenge_token: str, credential: dict, name: str = "Passkey") -> PasskeyCredential:
    row = get_security_challenge(challenge_token, SecurityChallenge.Purpose.WEBAUTHN_REGISTER)
    if not row or row.user_id != user.id:
        raise ValueError("Passkey registration challenge is invalid or expired.")
    rp_id, origin = webauthn_config()
    result = verify_registration_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(row.challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        require_user_verification=True,
    )
    record = PasskeyCredential.objects.create(
        user=user,
        name=(name or "Passkey")[:120],
        credential_id=bytes_to_base64url(result.credential_id),
        public_key=bytes_to_base64url(result.credential_public_key),
        sign_count=result.sign_count,
        device_type=str(result.credential_device_type or ""),
        backed_up=bool(result.credential_backed_up),
    )
    consume_security_challenge(row)
    return record


def begin_passkey_auth(user, *, preauth_token: str) -> tuple[str, dict]:
    credentials = list(PasskeyCredential.objects.filter(user=user, active=True))
    if not credentials:
        raise ValueError("No active passkeys are registered.")
    rp_id, _ = webauthn_config()
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(row.credential_id)) for row in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    raw = create_security_challenge(
        user=user,
        purpose=SecurityChallenge.Purpose.WEBAUTHN_AUTH,
        challenge=bytes_to_base64url(options.challenge),
        payload={"preauth_token": preauth_token},
        minutes=5,
    )
    return raw, json.loads(options_to_json(options))


def verify_passkey_auth(*, user, challenge_token: str, credential: dict) -> bool:
    row = get_security_challenge(challenge_token, SecurityChallenge.Purpose.WEBAUTHN_AUTH)
    if not row or row.user_id != user.id:
        return False
    cred_id = str(credential.get("id") or credential.get("rawId") or "")
    stored = PasskeyCredential.objects.filter(user=user, credential_id=cred_id, active=True).first()
    if not stored:
        return False
    rp_id, origin = webauthn_config()
    result = verify_authentication_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(row.challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=base64url_to_bytes(stored.public_key),
        credential_current_sign_count=stored.sign_count,
        require_user_verification=True,
    )
    stored.sign_count = result.new_sign_count
    stored.last_used_at = timezone.now()
    stored.save(update_fields=["sign_count", "last_used_at", "updated_at"])
    consume_security_challenge(row)
    return True
