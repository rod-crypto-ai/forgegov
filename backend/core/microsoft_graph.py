from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import ConnectedApp, Membership, Organization
from .security_services import decrypt_secret, encrypt_secret

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = [
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Mail.Send",
    "Calendars.ReadWrite",
    "ChannelMessage.Send",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
]


class MicrosoftIntegrationError(RuntimeError):
    pass


def _client_id() -> str:
    return str(os.getenv("MICROSOFT_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return str(os.getenv("MICROSOFT_CLIENT_SECRET") or "").strip()


def _tenant() -> str:
    return str(os.getenv("MICROSOFT_TENANT_ID") or "organizations").strip() or "organizations"


def configured() -> bool:
    return bool(_client_id() and _client_secret())


def redirect_uri(request=None) -> str:
    explicit = str(os.getenv("MICROSOFT_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit
    if request is None:
        raise MicrosoftIntegrationError("MICROSOFT_REDIRECT_URI is required when no request is available.")
    return request.build_absolute_uri("/api/integrations/microsoft/callback/")


def _oauth_base(tenant: str | None = None) -> str:
    return f"https://login.microsoftonline.com/{tenant or _tenant()}/oauth2/v2.0"


def _state_key(state: str) -> str:
    return f"forgegov:microsoft-oauth:{state}"


def begin_authorization(*, user, organization: Organization, request) -> dict:
    if not configured():
        raise MicrosoftIntegrationError("Microsoft 365 is not configured by the ForgeGov administrator.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    callback = redirect_uri(request)
    cache.set(
        _state_key(state),
        {"user_id": user.id, "organization_id": organization.id, "verifier": verifier, "redirect_uri": callback},
        timeout=600,
    )
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": callback,
        "response_mode": "query",
        "scope": " ".join(DEFAULT_SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return {"authorization_url": f"{_oauth_base()}/authorize?{urlencode(params)}", "expires_in": 600}


def _token_post(data: dict, *, tenant: str | None = None) -> dict:
    try:
        response = requests.post(f"{_oauth_base(tenant)}/token", data=data, timeout=20)
    except requests.RequestException as exc:
        raise MicrosoftIntegrationError("Microsoft identity service could not be reached.") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise MicrosoftIntegrationError("Microsoft identity service returned invalid JSON.") from exc
    if not response.ok:
        detail = payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}"
        raise MicrosoftIntegrationError(f"Microsoft authorization failed: {str(detail)[:500]}")
    return payload


def complete_authorization(*, state: str, code: str) -> ConnectedApp:
    from django.contrib.auth import get_user_model

    pending = cache.get(_state_key(state))
    cache.delete(_state_key(state))
    if not pending:
        raise MicrosoftIntegrationError("Microsoft authorization state expired or was already used.")
    if not code:
        raise MicrosoftIntegrationError("Microsoft did not return an authorization code.")
    user = get_user_model().objects.filter(id=pending["user_id"]).first()
    organization = Organization.objects.filter(id=pending["organization_id"]).first()
    if not user or not organization:
        raise MicrosoftIntegrationError("The ForgeGov user or workspace no longer exists.")
    if organization.status in {Organization.Status.SUSPENDED, Organization.Status.CANCELLED} or not Membership.objects.filter(user=user, organization=organization, active=True).exists():
        raise MicrosoftIntegrationError("ForgeGov workspace access changed before Microsoft authorization completed. Start the connection again after access is restored.")
    token = _token_post({
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": pending["redirect_uri"],
        "code_verifier": pending["verifier"],
        "scope": " ".join(DEFAULT_SCOPES),
    })
    access_token = str(token.get("access_token") or "")
    refresh_token = str(token.get("refresh_token") or "")
    if not access_token or not refresh_token:
        raise MicrosoftIntegrationError("Microsoft did not return the delegated access required for a persistent connection.")
    profile = _raw_graph("GET", "/me", access_token=access_token)
    expires_in = max(60, int(token.get("expires_in") or 3600))
    connection, _ = ConnectedApp.objects.update_or_create(
        organization=organization,
        user=user,
        provider=ConnectedApp.Provider.MICROSOFT,
        defaults={
            "status": ConnectedApp.Status.CONNECTED,
            "external_account_id": str(profile.get("id") or "")[:255],
            "account_email": str(profile.get("mail") or profile.get("userPrincipalName") or "")[:254],
            "tenant_id": _tenant()[:255],
            "scopes": str(token.get("scope") or " ".join(DEFAULT_SCOPES)).split(),
            "access_token_encrypted": encrypt_secret(access_token),
            "refresh_token_encrypted": encrypt_secret(refresh_token),
            "token_expires_at": timezone.now() + timedelta(seconds=expires_in),
            "last_error": "",
            "connected_at": timezone.now(),
            "disconnected_at": None,
        },
    )
    metadata = dict(connection.metadata or {})
    metadata.update({
        "verified_at": timezone.now().isoformat(),
        "verified_account_id": connection.external_account_id,
        "verified_account_email": connection.account_email,
    })
    connection.metadata = metadata
    connection.save(update_fields=["metadata", "updated_at"])
    return connection


def connection_for(*, user, organization: Organization, require_connected: bool = True) -> ConnectedApp | None:
    row = ConnectedApp.objects.filter(user=user, organization=organization, provider=ConnectedApp.Provider.MICROSOFT).first()
    if require_connected and (not row or row.status != ConnectedApp.Status.CONNECTED):
        raise MicrosoftIntegrationError("Connect Microsoft 365 in Settings before using this action.")
    return row


def public_status(*, user, organization: Organization) -> dict:
    row = connection_for(user=user, organization=organization, require_connected=False)
    metadata = dict(row.metadata or {}) if row else {}
    scopes = list(row.scopes or []) if row else []
    scope_names = {str(scope).lower() for scope in scopes}
    return {
        "provider": "microsoft",
        "configured": configured(),
        "connected": bool(row and row.status == ConnectedApp.Status.CONNECTED),
        "verified": bool(row and row.status == ConnectedApp.Status.CONNECTED and metadata.get("verified_at")),
        "verified_at": metadata.get("verified_at"),
        "status": row.status if row else "not_connected",
        "account_email": row.account_email if row else "",
        "scopes": scopes,
        "connected_at": row.connected_at if row else None,
        "last_error": row.last_error if row else "",
        "default_team_id": metadata.get("default_team_id", ""),
        "default_team_name": metadata.get("default_team_name", ""),
        "default_channel_id": metadata.get("default_channel_id", ""),
        "default_channel_name": metadata.get("default_channel_name", ""),
        "capabilities": {
            "outlook_mail": "mail.send" in scope_names,
            "outlook_calendar": "calendars.readwrite" in scope_names,
            "teams_channel_message": "channelmessage.send" in scope_names,
        },
    }


def verify_connection(row: ConnectedApp) -> ConnectedApp:
    profile = graph_request(row, "GET", "/me")
    account_email = str(profile.get("mail") or profile.get("userPrincipalName") or "")[:254]
    external_account_id = str(profile.get("id") or "")[:255]
    metadata = dict(row.metadata or {})
    metadata.update({
        "verified_at": timezone.now().isoformat(),
        "verified_account_id": external_account_id,
        "verified_account_email": account_email,
    })
    row.metadata = metadata
    if account_email:
        row.account_email = account_email
    if external_account_id:
        row.external_account_id = external_account_id
    row.status = ConnectedApp.Status.CONNECTED
    row.last_error = ""
    row.save(update_fields=["metadata", "account_email", "external_account_id", "status", "last_error", "updated_at"])
    return row


def disconnect(*, user, organization: Organization) -> None:
    row = connection_for(user=user, organization=organization, require_connected=False)
    if not row:
        return
    row.status = ConnectedApp.Status.DISCONNECTED
    row.access_token_encrypted = ""
    row.refresh_token_encrypted = ""
    row.token_expires_at = None
    row.disconnected_at = timezone.now()
    row.last_error = ""
    row.save(update_fields=["status", "access_token_encrypted", "refresh_token_encrypted", "token_expires_at", "disconnected_at", "last_error", "updated_at"])


def _refresh(row: ConnectedApp) -> str:
    if not row.refresh_token_encrypted:
        row.status = ConnectedApp.Status.ERROR
        row.last_error = "Microsoft refresh authorization is missing. Reconnect Microsoft 365."
        row.save(update_fields=["status", "last_error", "updated_at"])
        raise MicrosoftIntegrationError(row.last_error)
    refresh_token = decrypt_secret(row.refresh_token_encrypted)
    token = _token_post({
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(DEFAULT_SCOPES),
    }, tenant=row.tenant_id or None)
    access_token = str(token.get("access_token") or "")
    if not access_token:
        raise MicrosoftIntegrationError("Microsoft did not return a refreshed access token.")
    row.access_token_encrypted = encrypt_secret(access_token)
    if token.get("refresh_token"):
        row.refresh_token_encrypted = encrypt_secret(str(token["refresh_token"]))
    row.token_expires_at = timezone.now() + timedelta(seconds=max(60, int(token.get("expires_in") or 3600)))
    row.scopes = str(token.get("scope") or " ".join(row.scopes or DEFAULT_SCOPES)).split()
    row.status = ConnectedApp.Status.CONNECTED
    row.last_error = ""
    row.save(update_fields=["access_token_encrypted", "refresh_token_encrypted", "token_expires_at", "scopes", "status", "last_error", "updated_at"])
    return access_token


def access_token(row: ConnectedApp) -> str:
    if row.status != ConnectedApp.Status.CONNECTED:
        raise MicrosoftIntegrationError("Microsoft 365 is not connected.")
    if row.token_expires_at and row.token_expires_at > timezone.now() + timedelta(minutes=2) and row.access_token_encrypted:
        return decrypt_secret(row.access_token_encrypted)
    return _refresh(row)


def _raw_graph(method: str, path: str, *, access_token: str, json_body: dict | None = None, params: dict | None = None):
    try:
        response = requests.request(
            method,
            f"{GRAPH_ROOT}{path}",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=json_body,
            params=params,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MicrosoftIntegrationError("Microsoft Graph could not be reached.") from exc
    if response.status_code == 204:
        return {}
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        detail = ((payload.get("error") or {}).get("message") if isinstance(payload.get("error"), dict) else "") or f"HTTP {response.status_code}"
        raise MicrosoftIntegrationError(f"Microsoft Graph request failed: {str(detail)[:500]}")
    return payload


def graph_request(row: ConnectedApp, method: str, path: str, *, json_body: dict | None = None, params: dict | None = None):
    try:
        result = _raw_graph(method, path, access_token=access_token(row), json_body=json_body, params=params)
        if row.last_error:
            row.last_error = ""
            row.save(update_fields=["last_error", "updated_at"])
        return result
    except MicrosoftIntegrationError as exc:
        row.last_error = str(exc)[:1000]
        row.save(update_fields=["last_error", "updated_at"])
        raise


def list_teams(row: ConnectedApp) -> list[dict]:
    payload = graph_request(row, "GET", "/me/joinedTeams")
    return [{"id": str(x.get("id") or ""), "name": str(x.get("displayName") or "")} for x in payload.get("value", []) if x.get("id")]


def list_channels(row: ConnectedApp, team_id: str) -> list[dict]:
    if not team_id:
        return []
    payload = graph_request(row, "GET", f"/teams/{team_id}/channels")
    return [{"id": str(x.get("id") or ""), "name": str(x.get("displayName") or "")} for x in payload.get("value", []) if x.get("id")]


def configure_defaults(row: ConnectedApp, data: dict) -> dict:
    metadata = dict(row.metadata or {})
    for key in ("default_team_id", "default_team_name", "default_channel_id", "default_channel_name"):
        if key in data:
            metadata[key] = str(data.get(key) or "")[:500]
    row.metadata = metadata
    row.save(update_fields=["metadata", "updated_at"])
    return metadata


def send_mail(row: ConnectedApp, *, to: list[str], subject: str, body: str) -> None:
    recipients = [{"emailAddress": {"address": address.strip()}} for address in to if address and "@" in address]
    if not recipients:
        raise MicrosoftIntegrationError("At least one valid Outlook recipient is required.")
    graph_request(row, "POST", "/me/sendMail", json_body={
        "message": {
            "subject": str(subject or "ForgeGov opportunity update")[:255],
            "body": {"contentType": "Text", "content": str(body or "")[:50000]},
            "toRecipients": recipients,
        },
        "saveToSentItems": True,
    })


def create_event(row: ConnectedApp, *, subject: str, start: str, end: str, timezone_name: str = "UTC", body: str = "", attendees: list[str] | None = None) -> dict:
    if not start or not end:
        raise MicrosoftIntegrationError("Start and end times are required for an Outlook calendar event.")
    attendee_rows = [{"emailAddress": {"address": a.strip()}, "type": "required"} for a in (attendees or []) if a and "@" in a]
    return graph_request(row, "POST", "/me/events", json_body={
        "subject": str(subject or "ForgeGov capture milestone")[:255],
        "body": {"contentType": "Text", "content": str(body or "")[:50000]},
        "start": {"dateTime": start, "timeZone": timezone_name or "UTC"},
        "end": {"dateTime": end, "timeZone": timezone_name or "UTC"},
        "attendees": attendee_rows,
    })


def send_channel_message(row: ConnectedApp, *, team_id: str, channel_id: str, message: str) -> dict:
    metadata = dict(row.metadata or {})
    team_id = team_id or str(metadata.get("default_team_id") or "")
    channel_id = channel_id or str(metadata.get("default_channel_id") or "")
    if not team_id or not channel_id:
        raise MicrosoftIntegrationError("Choose a default Microsoft Teams team and channel in Settings first.")
    content = "<p>" + html.escape(str(message or "")[:50000]).replace("\n", "<br>") + "</p>"
    return graph_request(row, "POST", f"/teams/{team_id}/channels/{channel_id}/messages", json_body={"body": {"contentType": "html", "content": content}})
