# ForgeGov Microsoft 365 Setup

ForgeGov v3.2.1.1 uses a confidential server-side Microsoft Entra application with delegated Microsoft Graph access.

## 1. Register the application

In Microsoft Entra admin center → App registrations, create an application for ForgeGov. For a SaaS deployment serving multiple customer Microsoft 365 tenants, select organizational-directory accounts (multitenant).

Add a **Web** redirect URI matching the ForgeGov API callback exactly:

```text
https://YOUR_API_HOST/api/integrations/microsoft/callback/
```

Local development can use:

```text
http://localhost:8000/api/integrations/microsoft/callback/
```

## 2. Delegated Microsoft Graph permissions

Configure delegated permissions:
- `User.Read`
- `Mail.Send`
- `Calendars.ReadWrite`
- `ChannelMessage.Send`
- `Team.ReadBasic.All`
- `Channel.ReadBasic.All`

ForgeGov also requests the OIDC/OAuth scopes `openid`, `profile`, and `offline_access` during authorization. Microsoft tenant policy may require administrator consent for some Graph scopes.

## 3. Create the client credential

Create a Microsoft Entra client secret and store it only in the ForgeGov backend deployment environment. Never put it in `NEXT_PUBLIC_*`, frontend source, Git, or a browser-accessible endpoint.

## 4. ForgeGov environment

Set on the backend service:

```text
MICROSOFT_CLIENT_ID=<Application (client) ID>
MICROSOFT_CLIENT_SECRET=<client secret value>
MICROSOFT_TENANT_ID=organizations
MICROSOFT_REDIRECT_URI=https://YOUR_API_HOST/api/integrations/microsoft/callback/
```

The Render Blueprint marks the client ID, client secret, and redirect URI for environment configuration. The secret is not stored in source.

## 5. User connection

After deployment:
1. Sign in to ForgeGov.
2. Open Settings → Connected Apps.
3. Select **Connect Microsoft 365**.
4. Complete Microsoft consent.
5. Choose a default Microsoft Team and channel.
6. Use **Microsoft 365** from an opportunity workspace to send Outlook email, create an Outlook calendar event, or share to Teams.

Connections are user/workspace scoped. ForgeGov administrators do not automatically gain access to an employee's Microsoft mailbox or Teams account.


## Connection verification

After Microsoft redirects back to ForgeGov, v3.2.1.2 verifies the saved delegated authorization against Microsoft Graph `/me`. Settings should display **Connected · Verified** and the signed-in account. If authorization fails, the callback error is displayed in Settings instead of being silently discarded.
