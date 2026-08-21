# ForgeGov v3.1.2 Validation

The v3.1.2 release gate contains 19 stages: source/release identity, source audit, Compose validation, service builds, startup, Django/migration checks, full backend regression, historical release regressions, dedicated v3.1.2 notification tests, frontend lint/typecheck/build, production Django security checks, backend/frontend dependency audits, tracked-secret scan, non-root runtime checks, database backup/isolated restore, and final health/readiness/container status.

Successful completion ends with:

`ForgeGov v3.1.2 validation completed successfully.`
