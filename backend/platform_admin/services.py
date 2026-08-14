from django.utils import timezone
from .models import PlatformAuditEvent, FeatureFlag, PlatformSetting


DEFAULT_FLAGS = (
    ("forgeai", "ForgeAI", True),
    ("pricing", "Pricing", True),
    ("proposal-tools", "Proposal tools", True),
    ("project-rooms", "Project Rooms", True),
    ("executive-portfolio", "Executive Portfolio", True),
    ("advanced-award-intelligence", "Advanced Award Intelligence", True),
    ("grants", "Grants", True),
    ("subnet", "SUBNet", True),
    ("awards", "Awards", True),
    ("forecasts", "Forecasts", True),
    ("contract-vehicles", "Contract Vehicles", True),
    ("network", "Network", True),
    ("experimental", "Experimental features", False),
)


def seed_defaults():
    for key, name, enabled in DEFAULT_FLAGS:
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={"name": name, "enabled": enabled},
        )
    PlatformSetting.objects.get_or_create(
        key="platform_mode",
        defaults={"value": {"mode": "normal"}},
    )


def audit(request, action, *, target_type="", target_id="", organization=None, reason="", metadata=None):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return PlatformAuditEvent.objects.create(
        actor=request.user if getattr(request.user, "is_authenticated", False) else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        organization=organization,
        reason=reason or "",
        metadata=metadata or {},
        ip_address=ip or None,
    )


def platform_mode():
    setting = PlatformSetting.objects.filter(key="platform_mode").first()
    return (setting.value or {}).get("mode", "normal") if setting else "normal"


def feature_enabled(key):
    flag = FeatureFlag.objects.filter(key=key).first()
    return bool(flag.enabled) if flag else False
