# ForgeGov v1.2.1 — Render Deployment Hotfix

This release retains the v1.2.0 intelligence expansion and fixes Render production deployment failures.

## Fixed

- Render health checks now remain available while a custom API domain is being applied.
- Django automatically accepts the Render-generated hostname and an `API_PUBLIC_URL` hostname.
- Blueprint domain settings are no longer hardcoded, preventing syncs from overwriting existing custom-domain values.
- Gunicorn respects Render’s `WEB_CONCURRENCY` setting instead of forcing three workers.
- Celery worker concurrency is limited to one process to reduce memory pressure on small instances.
- Celery startup retries its broker connection and uses safer task acknowledgment settings.
- Celery Beat stores its PID and schedule under `/tmp`, avoiding read-only or stale-file failures.
- Database migrations retry during transient database startup failures.
- Static files are collected during image build and service startup.

## Required Render values

The Blueprint intentionally marks deployment-specific domain values as `sync: false`. Preserve or enter these in Render:

- `API_PUBLIC_URL` — existing public API URL, such as `https://api.example.com`
- `DJANGO_ALLOWED_HOSTS` — comma-separated hostnames without schemes
- `FRONTEND_URL` — public frontend origin
- `CORS_ALLOWED_ORIGINS` — public frontend origin(s)
- `CSRF_TRUSTED_ORIGINS` — public frontend origin(s)
- `NEXT_PUBLIC_API_BASE_URL` — existing API URL ending in `/api`
