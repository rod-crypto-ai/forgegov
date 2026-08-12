# ForgeGov v3.0.2 Security Configuration

Recommended private-beta production values:

```env
REGISTRATION_MODE=private_beta
BUSINESS_EMAIL_REQUIRED=false

TERMS_VERSION=2026-08-12
PRIVACY_VERSION=2026-08-12

EMAIL_VERIFICATION_TOKEN_MINUTES=60
PASSWORD_RESET_TOKEN_MINUTES=30

AXES_ENABLED=true
AXES_FAILURE_LIMIT=5
AXES_COOLOFF_MINUTES=15

AUTH_COOKIE_SAMESITE=Lax
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
```

## Important deployment notes

1. Keep `DJANGO_DEBUG=false` in production.
2. Use a strong `DJANGO_SECRET_KEY`.
3. Configure working transactional email before inviting external beta users.
4. Keep `REGISTRATION_MODE=private_beta` until the ForgeGov control plane and public-registration abuse controls are complete.
5. The operational Terms and Privacy pages included in this build are private-beta placeholders and should receive qualified legal review before unrestricted public launch.
6. v3.0.3 is the planned MFA / passkey / recovery-code milestone.
