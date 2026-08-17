# ForgeGov v3.0.7 Validation

## Static validation completed during build

- Python source compilation succeeds for the backend tree.
- New shell tooling passes `bash -n` syntax validation.
- `docker-compose.yml`, `docker-compose.production.yml`, and `render.yaml` parse as valid YAML.
- Frontend `package.json` and `package-lock.json` parse as valid JSON and report 3.0.7.
- No merge-conflict markers are present in backend, frontend, or scripts.
- Common test credential strings are redacted by the new observability helper.
- Runtime release identity is centralized in `backend/core/version.py` and set to 3.0.7.
- The accidental `SECURE_SECURE_REFERRER_POLICY` name is corrected to Django's `SECURE_REFERRER_POLICY`.
- v3.0.6 dependency hardening remains in place (`pypdf>=6.16.1,<7`, `cryptography>=50,<51`).

## Local Docker release gate

Run from the repository root:

```bash
./VERIFY_V3.0.7.command
```

The verifier performs:

1. Source/release identity validation.
2. Docker Compose validation.
3. Full service build.
4. Service startup.
5. Django system and migration-drift checks.
6. Existing core/platform-admin/v3.0.6 security regression tests.
7. v3.0.7 reliability tests.
8. Frontend lint, typecheck, and production build.
9. Non-root backend/worker/beat verification.
10. PostgreSQL backup plus isolated restore verification.
11. `/api/health/` and `/api/ready/` version/status smoke tests.
12. Final container status.

No release tag should be created until this local Docker gate passes.
