# ForgeGov v3.0.7 — Reliability, Monitoring & Recovery

## Mission

Make ForgeGov failures visible, degradable, and recoverable without turning optional upstream outages into full-platform outages.

## Delivered scope

- `/api/health/` remains a lightweight liveness endpoint.
- `/api/ready/` checks critical PostgreSQL and Redis/cache readiness and returns HTTP 503 when the API should not receive traffic.
- Docker Compose uses API readiness for backend health and frontend startup ordering.
- SearXNG is treated as an optional upstream; its outage no longer prevents the core API from starting.
- Platform Admin system operations includes database/cache readiness, Celery worker reachability, sync freshness, and existing connector health.
- Sync freshness uses existing `DataSyncRun` history and flags fresh/running/stale/failed/unknown states without a migration.
- Request correlation adds `X-Request-ID` and request duration/status logging.
- Production logging defaults to structured JSON; development logging remains readable plain text. Common credential formats are redacted.
- Local/self-hosted PostgreSQL backup creation and isolated restore verification scripts are included.
- Release smoke checks validate both health and readiness against the expected version.
- The release verifier runs source, Compose, Django, migration, backend, frontend, non-root-runtime, and health/readiness checks.

## Recovery workflow

Create a backup:

```bash
make backup
```

Verify that a backup can actually restore into an isolated temporary database:

```bash
make verify-backup BACKUP=backups/forgegov-YYYYMMDDTHHMMSSZ.dump
```

The restore-verification workflow never overwrites the live ForgeGov database. Managed production databases should continue to use the provider's native point-in-time backup/restore capability in addition to application-level validation.

## Rollback gate

Before a deployment, retain the previous Git tag and database backup. After deployment run:

```bash
EXPECTED_VERSION=3.0.7 ./scripts/release_smoke.sh
```

If health/readiness fails, redeploy the previous known-good Git tag. A database rollback is only required when a release includes an incompatible migration; v3.0.7 introduces no database migration.

## Release identity

`VERSION`, backend `core.version`, health/readiness responses, frontend package metadata, and validation require `3.0.7`.
