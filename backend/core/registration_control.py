from django.conf import settings

VALID_REGISTRATION_MODES = {"public", "private_beta", "invite_only", "closed"}


def effective_registration_mode():
    try:
        from platform_admin.models import PlatformSetting
        row = PlatformSetting.objects.filter(key="registration_mode").first()
        mode = str((row.value or {}).get("mode", "")).strip().lower() if row else ""
        if mode in VALID_REGISTRATION_MODES:
            return mode
    except Exception:
        pass
    mode = str(getattr(settings, "REGISTRATION_MODE", "private_beta")).strip().lower()
    return mode if mode in VALID_REGISTRATION_MODES else "private_beta"
