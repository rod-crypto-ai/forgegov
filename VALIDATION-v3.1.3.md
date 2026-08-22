# ForgeGov v3.1.3 Validation

The authoritative release test is:

```bash
./VERIFY_V3.1.3.command
```

The 20-stage gate validates release identity, source safeguards, Compose, service builds, migrations, historical regressions, v3.1.3 competitive-positioning tests, frontend lint/typecheck/build, Django production security, dependency/secret scans, non-root runtime, database backup/restore, and final health/readiness.

Do not commit, push, or tag v3.1.3 unless the verifier finishes with:

`ForgeGov v3.1.3 validation completed successfully.`
