# ForgeGov v1.0.1 — Critical Reliability and Security Fixes

## Fixed

- Django startup failure caused by DRF routers without explicit basenames.
- Opportunity searches now use authenticated, refresh-aware API requests.
- Frontend API calls, including the session `/auth/me/` check, automatically refresh expired access tokens without creating refresh loops.
- CSRF protection is enforced for cookie-authenticated unsafe requests, including login, registration, refresh, and logout.
- Refresh tokens are rotated and the previous token is blacklisted.
- Login and registration throttles were added and backed by shared Redis cache rather than per-process memory.
- Production rejects placeholder or undersized Django secret keys.
- SAM.gov date inputs from HTML date fields are converted to the required format, pagination values are normalized, and public opportunity links no longer prefer role-restricted API links. SAM.gov 404 “no data” responses now display an empty result set instead of a broken-search error.
- SAM.gov search throttle increased from an impractical 10 searches per day to a configurable 120 per hour.
- Viewer accounts can no longer create workflow records through function-based endpoints.
- Cross-workspace pipeline/task and nested relationship references are rejected.
- Shared public-data catalogs are read-only through the user API, preventing one tenant from deleting global opportunity, award, agency, vendor, participant, or category data.
- Team administrators can no longer promote themselves or others to workspace owner.
- Re-inviting the same email no longer causes an invitation uniqueness failure; only pending invitations are unique.
- Legacy owner-role invitations are rejected because ownership transfer requires a dedicated audited workflow.
- Saved grant searches reopen the Grants.gov search page rather than the SAM.gov page.
- Pagination now supports `page_size` with a safe maximum.
- Production frontend Docker image now performs a real Next.js build and Render starts its standalone server correctly.
- Database migrations no longer run concurrently in every worker and beat container.
- Internal package-registry URLs were removed from `package-lock.json`.
- The dashboard greeting now uses the signed-in user rather than a hardcoded name.
- Stale and broken installer, Makefile, and verification commands were replaced.
- Search-parameter routes now have Suspense boundaries so the production Next.js build can prerender them safely.
- CSV exports prefer ForgeGov’s normalized public SAM.gov source link.
- Verification no longer requires a host-side frontend dependency install before Docker builds the app.
- Post-login navigation now accepts internal application paths only.

## Verification included

Run:

```bash
./VERIFY.command
```

It validates source syntax, Docker Compose, backend checks/tests, frontend lint, a production frontend build, and local health endpoints.

## Known product limitations, not represented as completed features

- ForgeGov AI is still an interface-only workspace and does not call OpenAI yet.
- File records store metadata only; object storage, uploads, malware scanning, and document extraction are not implemented.
- Password recovery, email verification, MFA, billing, and workspace switching are not implemented.
- Federal forecasts, contract vehicles, and state/local connectors remain unconfigured placeholders.
