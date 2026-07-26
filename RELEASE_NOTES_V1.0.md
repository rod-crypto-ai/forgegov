# ForgeGov v1.0 — Secure Multi-User Launch

## Authentication
- Registration, sign-in, refresh, sign-out, and account profile endpoints.
- Secure HttpOnly access and refresh cookies.
- Protected frontend routes and persistent sessions.
- Password validation and disabled-account checks.

## Organizations and security
- A new organization workspace is created for public registrations.
- Team invitations support seven-day invitation links.
- Owner, Administrator, Capture Manager, Business Development, Proposal Writer, and Read Only roles.
- Organization-scoped pipeline, pursuits, tasks, saved searches, contacts, contact groups, teaming requests, and files.
- Viewer accounts receive read-only access.
- Audit logs for registration, login, profile changes, invitations, team changes, and membership changes.

## Launch preparation
- Render blueprint for frontend, backend, PostgreSQL, Redis, and Celery worker.
- Production CORS, CSRF, HTTPS, secure-cookie, HSTS, proxy, and allowed-host settings.
- Database migration and production entrypoint.
- Environment template for local and hosted deployment.

## Important
Before public deployment, set the actual Render frontend and backend hostnames in `render.yaml` if the default names are unavailable.
