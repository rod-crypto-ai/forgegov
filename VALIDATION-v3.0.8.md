# ForgeGov v3.0.8 Validation

Run `./VERIFY_V3.0.8.command` before release. It validates source identity, Compose, builds, Django/migrations, existing regressions, v3.0.7 reliability, v3.0.8 integrity/resilience, frontend lint/typecheck/build, non-root runtime, backup/restore, health/readiness, and container status.

Do not tag v3.0.8 unless the verifier completes successfully.
