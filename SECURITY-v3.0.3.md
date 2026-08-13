# ForgeGov v3.0.3 Security Configuration

Recommended production values:

```env
REGISTRATION_MODE=private_beta
AXES_ENABLED=true
AXES_FAILURE_LIMIT=5
AXES_COOLOFF_MINUTES=15
AUTH_COOKIE_SAMESITE=Lax

# Production WebAuthn values
WEBAUTHN_RP_ID=forge-gov.com
WEBAUTHN_ORIGIN=https://forge-gov.com
MFA_STEP_UP_MINUTES=10

SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
```

Local development:

```env
WEBAUTHN_RP_ID=localhost
WEBAUTHN_ORIGIN=http://localhost:3000
```

## Important

1. `WEBAUTHN_RP_ID` must match the relying-party domain used by the browser.
2. `WEBAUTHN_ORIGIN` must exactly match the frontend origin used during WebAuthn ceremonies.
3. TOTP secrets are encrypted at rest using a Fernet key derived from the deployment `DJANGO_SECRET_KEY`; changing that secret invalidates stored TOTP secrets.
4. Recovery codes are hashed and cannot be recovered from the database.
5. WebAuthn credential public keys are not secrets and are stored so the server can verify future assertions.
6. Do not enable company-wide MFA until recovery/support procedures have been tested.
7. No SMS fallback is included; recovery codes are the emergency factor for TOTP users.
