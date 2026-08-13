# ForgeGov v3.0.3 — MFA, Passkeys & Session Security

## Authentication hardening

- TOTP authenticator-app MFA using RFC-compatible time-based one-time passwords.
- One-time recovery codes stored only as SHA-256 hashes.
- WebAuthn passkey registration and MFA verification using `py_webauthn`.
- WebAuthn user verification is required for passkey ceremonies.
- Company-required MFA enrollment occurs before a normal ForgeGov workspace session is issued.
- Existing password + email-verification identity flow remains intact.

## Session security

- Every new/rotated ForgeGov refresh token is associated with a persistent `AuthSession`.
- Access/refresh JWTs carry a ForgeGov session identifier.
- Revoked/expired tracked sessions are rejected on every authenticated request.
- Existing v3.0.2 sessions are upgraded into tracked sessions at their next refresh.
- Security Center lists active sessions, IP, device/browser label, timestamps, and current-session state.
- Users can revoke an individual session or sign out all other sessions.

## Step-up authentication

Sensitive actions require recent reauthentication:

- passkey registration/removal
- authenticator removal
- recovery-code regeneration
- company security-policy changes
- revoking all other sessions

Step-up requires the current password and, when TOTP is enabled, an authenticator or recovery code. The default step-up window is 10 minutes.

## Company security policy

Owners/admins can control:

- company-wide MFA requirement
- privileged-role MFA requirement for Owner/Admin/Pricing roles
- tracked session maximum (bounded by the existing refresh-token lifetime)

Company-wide MFA cannot be enabled until all current active members have an MFA method. Future invited users are routed into MFA enrollment before they receive a normal workspace session.

## Security Center

New `/security` workspace:

- authenticator-app enrollment
- one-time recovery-code display/regeneration
- passkey management
- active-session management
- step-up authentication
- company MFA policy
- recent security audit activity

## Dependencies

- `pyotp>=2.9,<3`
- `cryptography>=46,<47`
- `webauthn>=2.2,<3`

These libraries provide the cryptographic/authenticator primitives while ForgeGov keeps its existing Django/DRF organization and JWT-cookie authorization architecture.

## Migration

- `core.0026_mfa_sessions_passkeys`

## Deliberately deferred

- SMS MFA
- passwordless passkey-only login
- SAML/OIDC enterprise SSO
- CAC/PIV
- external IAM replacement
- billing/subscription enforcement

Passwordless passkey-only login can use the same `PasskeyCredential` model later without changing the organization authorization architecture.
