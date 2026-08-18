# ForgeGov v3.1.0 Private Beta Production Readiness

## Launch gate
Run from the repository root:

```bash
./VERIFY_V3.1.0.command
```

Do not push or tag v3.1.0 unless the final line reports successful completion.

## Production requirements
- `DJANGO_DEBUG=false`
- strong unique `DJANGO_SECRET_KEY`
- explicit `DJANGO_ALLOWED_HOSTS`
- HTTPS `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`
- `PUBLIC_REGISTRATION_ENABLED=false` for private beta
- `REGISTRATION_MODE=private_beta` or `invite_only`
- `SECURE_SSL_REDIRECT=true`
- `SECURE_HSTS_SECONDS=31536000`
- PostgreSQL and Redis production services
- configured live connector credentials/endpoints required by enabled sources
- verified email delivery for verification and password recovery
- backup and isolated restore verification

## Required staging walkthrough
1. Register/invite a private-beta user, verify email, sign in, and complete MFA.
2. Test password reset and session revocation.
3. Search SAM.gov by keyword, solicitation number, State dropdown, and Set-Aside dropdown.
4. Open opportunity details/files, save a search, create an alert, and add an opportunity to pipeline.
5. Create pursuit/project room, invite a partner, exercise pricing/sensitive-document/export permissions, then revoke access.
6. Search Grants.gov, forecasts, contract vehicles, state/local sources, SUBNet/subawards, and award intelligence.
7. Exercise pricing, proposal/submission control, ForgeAI, reports, company/network, and Platform Admin health/governance.
8. Verify `/api/health/` and `/api/ready/`, create a backup, and perform isolated restore verification.

## External-source behavior
Government sources can rate-limit, block embedding, or experience outages. ForgeGov must show verified cached/indexed/degraded states and official-source fallback links instead of fabricated live records.
