from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .microsoft_graph import (
    MicrosoftIntegrationError,
    begin_authorization,
    complete_authorization,
    configure_defaults,
    connection_for,
    create_event,
    disconnect,
    list_channels,
    list_teams,
    public_status,
    send_channel_message,
    send_mail,
)
from .permissions import active_membership
from .models import Membership


def _membership(request):
    membership = active_membership(request.user)
    if not membership:
        raise MicrosoftIntegrationError("An active ForgeGov company workspace is required.")
    return membership


def _writable_membership(request):
    membership = _membership(request)
    if membership.role == Membership.Role.VIEWER:
        raise MicrosoftIntegrationError("Read-only users cannot send Microsoft 365 messages or create calendar events.")
    return membership


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft_status(request):
    try:
        membership = _membership(request)
        return Response(public_status(user=request.user, organization=membership.organization))
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft_connect(request):
    try:
        membership = _membership(request)
        return Response(begin_authorization(user=request.user, organization=membership.organization, request=request))
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([AllowAny])
def microsoft_callback(request):
    frontend = settings.FRONTEND_URL.rstrip("/") + "/settings"
    if request.query_params.get("error"):
        detail = str(request.query_params.get("error_description") or request.query_params.get("error") or "Microsoft authorization was cancelled.")[:500]
        return redirect(f"{frontend}?{urlencode({'microsoft': 'error', 'detail': detail})}")
    try:
        complete_authorization(state=str(request.query_params.get("state") or ""), code=str(request.query_params.get("code") or ""))
        return redirect(f"{frontend}?microsoft=connected")
    except MicrosoftIntegrationError as exc:
        return redirect(f"{frontend}?{urlencode({'microsoft': 'error', 'detail': str(exc)[:500]})}")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft_disconnect(request):
    try:
        membership = _membership(request)
        disconnect(user=request.user, organization=membership.organization)
        return Response({"disconnected": True})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft_teams(request):
    try:
        membership = _membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        return Response({"results": list_teams(connection)})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft_channels(request):
    try:
        membership = _membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        return Response({"results": list_channels(connection, str(request.query_params.get("team_id") or ""))})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def microsoft_defaults(request):
    try:
        membership = _membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        metadata = configure_defaults(connection, request.data or {})
        return Response({"saved": True, "metadata": metadata})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft_send_mail(request):
    try:
        membership = _writable_membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        recipients = request.data.get("to") or []
        if isinstance(recipients, str):
            recipients = [x.strip() for x in recipients.replace(";", ",").split(",") if x.strip()]
        send_mail(connection, to=list(recipients), subject=str(request.data.get("subject") or ""), body=str(request.data.get("body") or ""))
        return Response({"sent": True})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft_create_event(request):
    try:
        membership = _writable_membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        attendees = request.data.get("attendees") or []
        if isinstance(attendees, str):
            attendees = [x.strip() for x in attendees.replace(";", ",").split(",") if x.strip()]
        event = create_event(
            connection,
            subject=str(request.data.get("subject") or ""),
            start=str(request.data.get("start") or ""),
            end=str(request.data.get("end") or ""),
            timezone_name=str(request.data.get("timezone") or "UTC"),
            body=str(request.data.get("body") or ""),
            attendees=list(attendees),
        )
        return Response({"created": True, "event_id": event.get("id"), "web_link": event.get("webLink")})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def microsoft_send_teams(request):
    try:
        membership = _writable_membership(request)
        connection = connection_for(user=request.user, organization=membership.organization)
        result = send_channel_message(
            connection,
            team_id=str(request.data.get("team_id") or ""),
            channel_id=str(request.data.get("channel_id") or ""),
            message=str(request.data.get("message") or ""),
        )
        return Response({"sent": True, "message_id": result.get("id"), "web_url": result.get("webUrl")})
    except MicrosoftIntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
