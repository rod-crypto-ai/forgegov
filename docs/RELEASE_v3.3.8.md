# ForgeGov v3.3.8

Connection failures previously cleared the frontend session and redirected private pages to sign-in, even when the server session remained valid. Production logs confirmed successful token renewal followed by a client connection failure.

- Keep HTTP status on API errors so confirmed unauthorized responses remain distinguishable from network and service failures.
- Clear the local session and redirect to sign-in only after an authoritative 401 response.
- On interrupted verification, hide private content and show an accessible retry screen. Retry verifies the session again before restoring the workspace.
- Cover network interruption, HTTP 503, retry recovery, hidden private shell, narrow-screen layout, and confirmed 401 redirects in Chromium, Firefox, and WebKit.

No authentication lifetime, server permissions, subscription, schema, or payment changes. Rollback: c82d74ebf38ba3e0f4193d3f8241dbbaeac9fe83 (v3.3.7).

ForgeAI production requests still fail provider credential validation. Full scheduled ingestion coverage, historical stuck-run reconciliation, real Microsoft delivery, email delivery, and completed payments remain outstanding acceptance gates.
