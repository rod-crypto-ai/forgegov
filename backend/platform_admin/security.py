from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from core.models import AuthSession


def revoke_user_access(user):
    now = timezone.now()
    revoked_sessions = AuthSession.objects.filter(
        user=user,
        revoked_at__isnull=True,
    ).update(revoked_at=now, updated_at=now)

    blacklisted_tokens = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        blacklisted_tokens += int(created)

    was_active = bool(user.is_active)
    if was_active:
        user.is_active = False
        user.save(update_fields=["is_active"])

    return {
        "user_disabled": was_active,
        "revoked_sessions": revoked_sessions,
        "blacklisted_refresh_tokens": blacklisted_tokens,
    }


def restore_user_access(user):
    if user.is_active:
        return False
    user.is_active = True
    user.save(update_fields=["is_active"])
    return True
