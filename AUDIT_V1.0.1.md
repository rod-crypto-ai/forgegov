# ForgeGov v1.0.1 Audit Summary

The original v1.0 package was reviewed for startup, authentication, search, tenant isolation, deployment, and developer workflow defects.

## Critical defects corrected

1. Backend startup crash from missing DRF router basenames.
2. Search requests omitted credentials and failed behind authenticated endpoints.
3. Most API helpers did not refresh expired access tokens.
4. Cookie JWT requests did not enforce CSRF checks.
5. Team-role privilege escalation allowed administrators to assign owner access.
6. Cross-tenant foreign-key assignments were possible in several serializers and task creation.
7. Global public-data records were writable and deletable by ordinary authenticated users.
8. Production frontend image did not run `next build`.
9. Migrations ran redundantly and concurrently in backend, worker, and beat containers.
10. Frontend package lock referenced a private internal registry.
11. Existing backend tests no longer matched the authenticated API and would fail CI.
12. Invitation uniqueness prevented safe re-invitation after a prior accepted invite.
13. The Render frontend command bypassed the standalone image entry point and would fail at startup.
14. Production could accept the example secret value, and auth throttles used per-process memory instead of shared Redis.
15. Client routes using `useSearchParams` lacked Suspense boundaries and could fail a production Next.js build.
16. CSV exports still preferred SAM.gov role-restricted links over the normalized public source URL.
17. The verification script required host-side TypeScript packages before Docker installed dependencies.
18. The sign-in `next` parameter was not restricted to internal paths, creating an open-redirect/XSS risk.

## Functional defects corrected

- SAM.gov HTML date values were forwarded in the wrong format.
- The default live-search limit was too restrictive for normal use.
- Saved Grants.gov searches reopened the wrong opportunity source.
- Teaming creation fields did not match the backend model.
- Read-only catalogs displayed create forms that could never succeed.
- `page_size` query parameters were ignored.

## Validation status

- Python source compiles successfully.
- Static route, authentication, tenant, integration, deployment, and package-lock checks were completed.
- A full Docker runtime and Next.js dependency build must be run on the target Mac with `./VERIFY.command`; Docker is not available in the audit environment.
