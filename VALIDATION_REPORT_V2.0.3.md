# ForgeGov v2.0.3 validation report

## Artifact-environment checks completed

- Python compilation for the backend.
- Shell syntax for release and configuration scripts.
- JSON parsing for frontend package metadata and lockfile.
- YAML parsing for Docker Compose, Render, and SearXNG settings.
- TypeScript/TSX syntax transpilation across the frontend source tree.
- Static checks for v2.0.3 identity, grant routes, SearXNG configuration, SUBNet fallbacks, and removed obsolete error strings.

## Runtime checks required on the target Mac

This build environment cannot complete dependency installation because its npm mirror does not provide one locked package. It also does not expose the user's Docker daemon or configured government/API credentials. The included validator performs the authoritative runtime gate:

1. Django system check.
2. Migration check.
3. All 40 backend tests.
4. Frontend TypeScript check.
5. Frontend ESLint.
6. Next.js production build.
7. SearXNG JSON search probe when live web is enabled.
8. Docker container status.

Run:

```bash
./scripts/validate_release.sh
```

A release is not approved for deployment until the validator completes successfully on the target machine.
