from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import CollaborationNotification, Membership


def create_notification(*, organization, title, message, kind, link="", user=None, project_room=None):
    return CollaborationNotification.objects.create(
        organization=organization,
        user=user,
        project_room=project_room,
        title=title,
        message=message,
        kind=kind,
        link=link,
    )


def notify_organization_members(*, organization, title, message, kind, link="", project_room=None, roles=None):
    memberships = Membership.objects.filter(organization=organization, active=True).select_related("user")
    if roles:
        memberships = memberships.filter(role__in=roles)
    notifications=[]
    for membership in memberships:
        notifications.append(create_notification(
            organization=organization,
            user=membership.user,
            project_room=project_room,
            title=title,
            message=message,
            kind=kind,
            link=link,
        ))
    return notifications


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
