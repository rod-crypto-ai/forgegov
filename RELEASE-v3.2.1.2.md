# ForgeGov v3.2.1.2 — Microsoft 365 Connection Verification Hotfix

v3.2.1.2 is a focused hotfix for the Microsoft 365 Connected Apps flow introduced in v3.2.1.1. It does not change the roadmap or subcontracting/UX scope.

## Fixes

- The Settings page now surfaces Microsoft OAuth callback success and failure details instead of silently ignoring them.
- Successful callbacks are live-verified against Microsoft Graph and display the connected account.
- Connected Apps now reports `connected`, `verified`, `verified_at`, granted scopes, and capability availability without exposing tokens.
- Existing saved connections can be re-verified from Settings without reconnecting.
- Opportunity Microsoft 365 actions refresh connection state whenever the action opens instead of relying on stale page-mount state.
- The Microsoft action modal shows an explicit connection-checking state and live verification errors.
- Regression coverage now exercises the real callback persistence path with mocked Microsoft network responses instead of mocking away `complete_authorization`.

## Security

Tokens remain encrypted server-side and are never returned to the browser. Verification uses the delegated access token against Microsoft Graph `/me`; no additional Microsoft permission is introduced by this hotfix.

## Validation

Run `VERIFY_V3.2.1.2.command`. The existing 24-stage release gate is retained, with the Microsoft integration stage expanded to cover callback persistence and post-callback verification.
