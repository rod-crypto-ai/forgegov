# ForgeGov v3.0.9 Validation

## Static validation completed
- Backend Python source compiles successfully.
- Shell release/backup/restore/smoke scripts pass `bash -n`.
- Frontend package JSON and package-lock JSON parse successfully.
- Release identity is consistent at 3.0.9.
- Historical Platform Admin migration dependency is frozen to `core.0026_mfa_sessions_passkeys`; no `__latest__` migration dependency remains.
- v3.0.8 connector test-isolation correction is retained (`GET`/`POST` calls preserve existing mocks).
- No merge-conflict markers are present in backend/frontend/scripts.

## Local release gate required
Run `./VERIFY_V3.0.9.command` in the normal ForgeGov Docker environment before commit, push, or tag. The verifier performs:
1. source/release identity validation
2. Docker Compose validation
3. service builds/startup
4. Django + migration consistency checks
5. backend regression + v3.0.6 security tests
6. v3.0.7 reliability tests
7. v3.0.8 integrity/resilience tests
8. v3.0.9 governance/cross-tenant tests
9. frontend lint/typecheck/build
10. non-root runtime checks
11. backup + isolated restore verification
12. health/readiness smoke checks
13. final container status
