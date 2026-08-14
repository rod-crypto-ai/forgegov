from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from core.models import Organization
from .models import (
    PlatformAdminGrant,
    OrganizationControlState,
    UserControlState,
    BetaApplication,
    FeatureFlag,
    PlatformSetting,
    PlatformAuditEvent,
)
from .permissions import IsPlatformAdmin, IsPlatformSuperAdmin, active_platform_grant
from .services import audit, seed_defaults, platform_mode

User = get_user_model()


def _org_payload(org):
    state, _ = OrganizationControlState.objects.get_or_create(organization=org)
    beta = BetaApplication.objects.filter(organization=org).first()
    member_count = getattr(org, "member_count", None)
    if member_count is None:
        membership_rel = getattr(org, "memberships", None)
        member_count = membership_rel.count() if membership_rel is not None else 0
    return {
        "id": org.id,
        "name": getattr(org, "name", str(org)),
        "status": state.status,
        "beta_access": state.beta_access,
        "member_count": member_count,
        "approved_at": state.approved_at,
        "suspension_reason": state.suspension_reason,
        "updated_at": state.updated_at,
        "beta_status": beta.status if beta else None,
    }


def _user_payload(user):
    state, _ = UserControlState.objects.get_or_create(user=user)
    grant = PlatformAdminGrant.objects.filter(user=user, is_active=True).first()
    return {
        "id": user.id,
        "email": getattr(user, "email", ""),
        "first_name": getattr(user, "first_name", ""),
        "last_name": getattr(user, "last_name", ""),
        "is_active": getattr(user, "is_active", True),
        "last_login": getattr(user, "last_login", None),
        "date_joined": getattr(user, "date_joined", None),
        "platform_status": state.status,
        "platform_role": "super_admin" if getattr(user, "is_superuser", False) else (grant.role if grant else None),
        "mfa_verified": True if getattr(user, "is_superuser", False) else bool(grant and grant.mfa_verified),
    }


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def me(request):
    return Response({
        "platform_admin": True,
        "role": active_platform_grant(request.user),
        "maintenance_mode": platform_mode(),
    })


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def dashboard(request):
    seed_defaults()
    org_total = Organization.objects.count()
    states = dict(
        OrganizationControlState.objects.values_list("status").annotate(total=Count("id"))
    )
    user_states = dict(
        UserControlState.objects.values_list("status").annotate(total=Count("id"))
    )
    return Response({
        "organizations": {
            "total": org_total,
            "active": OrganizationControlState.objects.filter(status=OrganizationControlState.Status.ACTIVE).count(),
            "pending": OrganizationControlState.objects.filter(status=OrganizationControlState.Status.PENDING).count(),
            "suspended": OrganizationControlState.objects.filter(status=OrganizationControlState.Status.SUSPENDED).count(),
        },
        "users": {
            "total": User.objects.count(),
            "active": UserControlState.objects.filter(status=UserControlState.Status.ACTIVE).count(),
            "suspended": UserControlState.objects.filter(status=UserControlState.Status.SUSPENDED).count(),
        },
        "beta_pending": BetaApplication.objects.filter(status=BetaApplication.Status.PENDING).count(),
        "feature_flags": FeatureFlag.objects.count(),
        "recent_events": list(PlatformAuditEvent.objects.values(
            "id", "action", "target_type", "target_id", "reason", "created_at"
        )[:12]),
        "platform_mode": platform_mode(),
    })


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def organizations(request):
    qs = Organization.objects.all().order_by("id")
    q = request.query_params.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    return Response({"results": [_org_payload(org) for org in qs[:500]]})


@api_view(["POST"])
@permission_classes([IsPlatformSuperAdmin])
def organization_action(request, organization_id):
    org = Organization.objects.filter(pk=organization_id).first()
    if not org:
        return Response({"detail": "Organization not found."}, status=404)

    action = str(request.data.get("action", "")).strip().lower()
    reason = str(request.data.get("reason", "")).strip()
    notes = str(request.data.get("notes", "")).strip()
    state, _ = OrganizationControlState.objects.get_or_create(organization=org)

    transitions = {
        "approve": OrganizationControlState.Status.APPROVED,
        "activate": OrganizationControlState.Status.ACTIVE,
        "reject": OrganizationControlState.Status.REJECTED,
        "suspend": OrganizationControlState.Status.SUSPENDED,
        "disable": OrganizationControlState.Status.DISABLED,
        "reactivate": OrganizationControlState.Status.ACTIVE,
    }
    if action not in transitions:
        return Response({"detail": "Unsupported organization action."}, status=400)

    state.status = transitions[action]
    state.last_reviewed_at = timezone.now()
    state.last_reviewed_by = request.user
    if notes:
        state.internal_notes = notes
    if action == "approve":
        state.beta_access = True
        state.approved_at = timezone.now()
        state.approved_by = request.user
    if action == "suspend":
        state.suspension_reason = reason
    if action == "reactivate":
        state.suspension_reason = ""
    state.save()

    beta = BetaApplication.objects.filter(organization=org).first()
    if beta and action in {"approve", "reject"}:
        beta.status = BetaApplication.Status.APPROVED if action == "approve" else BetaApplication.Status.REJECTED
        beta.reviewed_at = timezone.now()
        beta.reviewed_by = request.user
        beta.save()

    audit(
        request,
        f"organization.{action}",
        target_type="organization",
        target_id=org.id,
        organization=org,
        reason=reason,
        metadata={"notes": notes},
    )
    return Response(_org_payload(org))


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def users(request):
    qs = User.objects.all().order_by("id")
    q = request.query_params.get("q", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    return Response({"results": [_user_payload(user) for user in qs[:500]]})


@api_view(["POST"])
@permission_classes([IsPlatformSuperAdmin])
def user_action(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return Response({"detail": "User not found."}, status=404)
    if user.pk == request.user.pk and request.data.get("action") in {"suspend", "disable"}:
        return Response({"detail": "You cannot suspend or disable your own platform-admin account."}, status=400)

    action = str(request.data.get("action", "")).strip().lower()
    reason = str(request.data.get("reason", "")).strip()
    state, _ = UserControlState.objects.get_or_create(user=user)
    transitions = {
        "activate": UserControlState.Status.ACTIVE,
        "reactivate": UserControlState.Status.ACTIVE,
        "suspend": UserControlState.Status.SUSPENDED,
        "disable": UserControlState.Status.DISABLED,
    }
    if action not in transitions:
        return Response({"detail": "Unsupported user action."}, status=400)

    state.status = transitions[action]
    state.reason = reason if action in {"suspend", "disable"} else ""
    state.updated_by = request.user
    state.save()
    audit(request, f"user.{action}", target_type="user", target_id=user.id, reason=reason)
    return Response(_user_payload(user))


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def beta_applications(request):
    results = []
    for beta in BetaApplication.objects.select_related("organization", "reviewed_by").order_by("-submitted_at")[:500]:
        results.append({
            "id": beta.id,
            "organization_id": beta.organization_id,
            "organization_name": getattr(beta.organization, "name", str(beta.organization)),
            "status": beta.status,
            "applicant_email": beta.applicant_email,
            "application_notes": beta.application_notes,
            "internal_notes": beta.internal_notes,
            "requested_information": beta.requested_information,
            "submitted_at": beta.submitted_at,
            "reviewed_at": beta.reviewed_at,
        })
    return Response({"results": results})


@api_view(["POST"])
@permission_classes([IsPlatformSuperAdmin])
def beta_action(request, application_id):
    beta = BetaApplication.objects.select_related("organization").filter(pk=application_id).first()
    if not beta:
        return Response({"detail": "Beta application not found."}, status=404)
    action = str(request.data.get("action", "")).strip().lower()
    notes = str(request.data.get("notes", "")).strip()
    requested_information = str(request.data.get("requested_information", "")).strip()

    mapping = {
        "approve": BetaApplication.Status.APPROVED,
        "reject": BetaApplication.Status.REJECTED,
        "request_info": BetaApplication.Status.NEEDS_INFO,
    }
    if action not in mapping:
        return Response({"detail": "Unsupported beta action."}, status=400)

    beta.status = mapping[action]
    beta.internal_notes = notes
    beta.requested_information = requested_information
    beta.reviewed_at = timezone.now()
    beta.reviewed_by = request.user
    beta.save()

    state, _ = OrganizationControlState.objects.get_or_create(organization=beta.organization)
    if action == "approve":
        state.status = OrganizationControlState.Status.APPROVED
        state.beta_access = True
        state.approved_at = timezone.now()
        state.approved_by = request.user
        state.save()
    elif action == "reject":
        state.status = OrganizationControlState.Status.REJECTED
        state.beta_access = False
        state.save()

    audit(
        request,
        f"beta.{action}",
        target_type="beta_application",
        target_id=beta.id,
        organization=beta.organization,
        metadata={"requested_information": requested_information, "notes": notes},
    )
    return Response({"id": beta.id, "status": beta.status})


@api_view(["GET", "POST"])
@permission_classes([IsPlatformAdmin])
def feature_flags(request):
    seed_defaults()
    if request.method == "GET":
        return Response({"results": list(FeatureFlag.objects.order_by("name").values(
            "id", "key", "name", "description", "enabled", "updated_at"
        ))})

    if active_platform_grant(request.user) != "super_admin":
        return Response({"detail": "Platform Super Admin access is required."}, status=403)

    key = str(request.data.get("key", "")).strip()
    flag = FeatureFlag.objects.filter(key=key).first()
    if not flag:
        return Response({"detail": "Feature flag not found."}, status=404)
    flag.enabled = bool(request.data.get("enabled"))
    flag.updated_by = request.user
    flag.save()
    audit(request, "feature_flag.updated", target_type="feature_flag", target_id=flag.id, metadata={
        "key": flag.key, "enabled": flag.enabled
    })
    return Response({"key": flag.key, "enabled": flag.enabled})


@api_view(["GET", "POST"])
@permission_classes([IsPlatformAdmin])
def platform_state(request):
    setting, _ = PlatformSetting.objects.get_or_create(
        key="platform_mode", defaults={"value": {"mode": "normal"}}
    )
    if request.method == "GET":
        return Response({"mode": (setting.value or {}).get("mode", "normal")})
    if active_platform_grant(request.user) != "super_admin":
        return Response({"detail": "Platform Super Admin access is required."}, status=403)
    mode = str(request.data.get("mode", "")).lower()
    if mode not in {"normal", "maintenance"}:
        return Response({"detail": "Mode must be normal or maintenance."}, status=400)
    setting.value = {"mode": mode}
    setting.updated_by = request.user
    setting.save()
    audit(request, "platform.mode_changed", target_type="platform_setting", target_id=setting.id, metadata={"mode": mode})
    return Response({"mode": mode})


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def audit_events(request):
    rows = PlatformAuditEvent.objects.select_related("actor", "organization")[:500]
    return Response({"results": [{
        "id": row.id,
        "action": row.action,
        "actor_email": getattr(row.actor, "email", "") if row.actor else "",
        "target_type": row.target_type,
        "target_id": row.target_id,
        "organization_id": row.organization_id,
        "reason": row.reason,
        "metadata": row.metadata,
        "ip_address": row.ip_address,
        "created_at": row.created_at,
    } for row in rows]})


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def system_operations(request):
    payload = {"connectors": [], "source": "ForgeGov connector registry", "probe": True}
    try:
        from core.intelligence.services.connectors import connector_health
        data = connector_health(probe=True)
        payload["connectors"] = data.get("connectors", data) if isinstance(data, dict) else data
    except Exception as exc:
        payload["connector_error"] = f"{type(exc).__name__}: connector health could not be loaded"

    try:
        from core.intelligence.services.award_ingestion import connector_registry_payload
        payload["connector_registry"] = connector_registry_payload(probe=True)
    except Exception:
        pass
    return Response(payload)
