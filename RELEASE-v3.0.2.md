# ForgeGov v3.0.2 — Identity & Account Foundation

## What changed

### Verified identity lifecycle
- Full name, email, password, Terms acceptance, and Privacy acknowledgement are required at registration.
- Public self-registration no longer receives workspace access immediately.
- Email verification uses short-lived, one-time tokens stored only as SHA-256 hashes.
- Email-bound company invitations act as mailbox possession proof and can activate the invited identity immediately.
- Registration lifecycle states are persisted separately from the Django user record.

### Controlled registration
`REGISTRATION_MODE` supports:
- `private_beta` — valid company invitation required
- `invite_only` — valid company invitation required
- `public` — self-service registration with email verification
- `closed` — valid company invitation required until the platform control plane is added

The v3.0.2 `.env.example` recommends `private_beta`.

### Company identity and joining
- Organization and user identities are separate.
- Organizations have lifecycle status: Trial, Active, Past Due, Suspended, Cancelled.
- Non-public business email domains can be bound to one organization.
- If a verified email domain matches an existing company, ForgeGov does not create a duplicate organization.
- The user verifies the mailbox first, then a company join request becomes visible to owners/admins.
- Domain matching is discovery only; it never grants access automatically.
- Owner/admin approval activates membership.

### Password security
- Minimum password length is 15 characters.
- Existing Django common-password, similarity, and numeric-password validators remain.
- No arbitrary uppercase/symbol composition rule was added.
- Password reset uses generic responses to resist account enumeration.
- Reset tokens are one-time and short-lived.
- Successful password reset blacklists outstanding refresh tokens when available.

### Login abuse protection
- `django-axes` added to the existing Django authentication flow.
- Redis-backed attempt tracking uses ForgeGov's existing shared cache.
- Default failure threshold: 5.
- Default cooloff: 15 minutes.
- Lockout is keyed to username + IP combination.
- DRF login throttle remains in place as an additional control.

### Account and organization enforcement
- Account status is checked on every JWT-authenticated request.
- Suspended/disabled/locked/deletion-pending accounts cannot continue using a previously issued access token.
- Suspended and cancelled organizations are excluded from active workspace permissions and workspace switching.

### Security audit events
New security events include:
- registration created
- email verification resent
- email verified
- login success
- login failure
- login blocked: unverified identity
- login blocked: account state
- login blocked: organization state
- password reset requested
- password changed via reset
- logout

### Account UI
- New verified identity / account-security summary in Profile & Workspace.
- Forgot Password, Reset Password, and Verify Email experiences.
- Registration shows controlled-access mode when private beta/invite-only mode is enabled.
- Registration explains company domain matching and approval.
- Pricing Manager and Contributor role presets added while existing role values remain compatible.

## API
- `GET /api/auth/registration-config/`
- `POST /api/auth/verify-email/`
- `POST /api/auth/resend-verification/`
- `POST /api/auth/password-reset/request/`
- `POST /api/auth/password-reset/confirm/`
- `GET /api/auth/security/`

## Migration
- `core.0025_identity_account_foundation`
- `django-axes` also contributes its own package migrations.

## Deliberately deferred
v3.0.2 does **not** add:
- MFA/TOTP
- WebAuthn/passkeys
- recovery codes
- active-session management UI
- SMS verification
- Stripe/billing
- SAML/OIDC enterprise SSO
- external IAM providers
- platform beta-application console

Those remain separate milestones so identity foundation can be validated before adding new authenticators.
