# ForgeGov v1.2.2 — Render Startup Command Fix

This hotfix removes Render `dockerCommand` overrides for the Django API, Celery worker, and Celery Beat services.

## Root cause

The v1.2.1 API command used nested shell quoting. Render passed the quoted Gunicorn line to `/bin/sh` as one command name, producing exit status 127 even though Gunicorn was installed.

## Fix

- `SERVICE_ROLE=web|worker|beat` selects the process in `backend/entrypoint.sh`.
- API binds to `${PORT:-8000}` and honors `${WEB_CONCURRENCY:-1}`.
- Worker runs with concurrency 1 and bounded child recycling.
- Beat stores PID and schedule files under `/tmp`.
- Render no longer needs to parse custom backend Docker commands.
