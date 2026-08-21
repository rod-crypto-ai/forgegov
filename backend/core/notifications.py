from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from .models import (
    CollaborationNotification,
    Membership,
    NotificationDelivery,
    NotificationPreference,
    ProjectRoomMember,
    ProjectRoomPartner,
)

CATEGORY_FIELD = {
    "opportunity": "opportunity_alerts",
    "opportunity_change": "opportunity_changes",
    "deadline": "deadlines",
    "pipeline": "pipeline",
    "project_room": "project_room",
    "security": "security",
}



def platform_notifications_enabled() -> bool:
    try:
        from platform_admin.models import PlatformSetting
        row = PlatformSetting.objects.filter(key="notifications_enabled").first()
        if not row:
            return True
        value = row.value or {}
        return bool(value.get("enabled", True))
    except Exception:
        return True

def notification_preference(*, organization, user) -> NotificationPreference:
    row, _ = NotificationPreference.objects.get_or_create(organization=organization, user=user)
    return row


def category_enabled(preference: NotificationPreference, category: str) -> bool:
    field = CATEGORY_FIELD.get(str(category or "").strip().lower())
    return bool(getattr(preference, field, True)) if field else True


def create_notification(*, organization, title, message, kind, link="", user=None, project_room=None, category=""):
    if not platform_notifications_enabled():
        return None
    if user is not None:
        preference = notification_preference(organization=organization, user=user)
        if not preference.in_app_enabled or not category_enabled(preference, category or kind):
            return None
    return CollaborationNotification.objects.create(
        organization=organization,
        user=user,
        project_room=project_room,
        title=title,
        message=message,
        kind=kind,
        link=link,
    )


def notify_organization_members(*, organization, title, message, kind, link="", project_room=None, roles=None, category="", exclude_user=None):
    memberships = Membership.objects.filter(organization=organization, active=True).select_related("user")
    if roles:
        memberships = memberships.filter(role__in=roles)
    if exclude_user is not None:
        memberships = memberships.exclude(user=exclude_user)
    notifications = []
    for membership in memberships:
        row = create_notification(
            organization=organization,
            user=membership.user,
            project_room=project_room,
            title=title,
            message=message,
            kind=kind,
            link=link,
            category=category,
        )
        if row is not None:
            notifications.append(row)
    return notifications


def _room_memberships(room, *, include_partners: bool):
    owner_q = Q(organization=room.owner_organization, active=True) & (
        Q(role__in=[Membership.Role.OWNER, Membership.Role.ADMIN]) |
        Q(project_room_memberships__project_room=room)
    )
    query = owner_q
    if include_partners:
        partner_org_ids = ProjectRoomPartner.objects.filter(
            project_room=room,
            revoked_at__isnull=True,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).values_list("organization_id", flat=True)
        partner_q = Q(organization_id__in=partner_org_ids, active=True) & (
            Q(role__in=[Membership.Role.OWNER, Membership.Role.ADMIN]) |
            Q(project_room_memberships__project_room=room)
        )
        query |= partner_q
    return Membership.objects.filter(query).select_related("user", "organization").distinct()


def notify_project_room_participants(*, room, actor, title, message, kind="project_room", link="", visibility="shared"):
    include_partners = visibility == "shared"
    rows = []
    for membership in _room_memberships(room, include_partners=include_partners):
        if actor is not None and membership.user_id == actor.id:
            continue
        row = create_notification(
            organization=membership.organization,
            user=membership.user,
            project_room=room,
            title=title,
            message=message,
            kind=kind,
            link=link or f"/project-rooms/{room.id}",
            category="project_room",
        )
        if row is not None:
            rows.append(row)
    return rows


def send_system_email(*, subject, message, recipient, html_message=None):
    if not recipient:
        return False
    try:
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "ForgeGov <noreply@forge-gov.com>"),
            [recipient],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception:
        return False


def send_tracked_email(*, subject, message, recipient, organization=None, user=None, category="", related_object_type="", related_object_id="", html_message=None):
    if not platform_notifications_enabled():
        NotificationDelivery.objects.create(
            organization=organization, user=user, channel="email", category=category, recipient=recipient or "",
            subject=subject[:255], status=NotificationDelivery.Status.SKIPPED,
            error_message="Notification delivery is disabled by the ForgeGov Creator.",
            related_object_type=related_object_type[:80], related_object_id=str(related_object_id or "")[:120],
        )
        return False
    if not recipient:
        NotificationDelivery.objects.create(
            organization=organization,
            user=user,
            channel="email",
            category=category,
            recipient="",
            subject=subject[:255],
            status=NotificationDelivery.Status.SKIPPED,
            error_message="No recipient email address is configured.",
            related_object_type=related_object_type[:80],
            related_object_id=str(related_object_id or "")[:120],
        )
        return False
    try:
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "ForgeGov <noreply@forge-gov.com>"),
            [recipient],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as exc:
        NotificationDelivery.objects.create(
            organization=organization,
            user=user,
            channel="email",
            category=category,
            recipient=recipient,
            subject=subject[:255],
            status=NotificationDelivery.Status.FAILED,
            error_message=str(exc)[:1000],
            related_object_type=related_object_type[:80],
            related_object_id=str(related_object_id or "")[:120],
        )
        return False
    NotificationDelivery.objects.create(
        organization=organization,
        user=user,
        channel="email",
        category=category,
        recipient=recipient,
        subject=subject[:255],
        status=NotificationDelivery.Status.SENT,
        related_object_type=related_object_type[:80],
        related_object_id=str(related_object_id or "")[:120],
        sent_at=timezone.now(),
    )
    return True
