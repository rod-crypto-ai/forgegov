# ForgeGov v1.0.2

ForgeGov is a government-contracting intelligence and capture-management platform built with Django, Django REST Framework, PostgreSQL, Redis, Celery, Next.js, TypeScript, and Docker.

## Working capabilities

- Secure registration, sign-in, sign-out, cookie JWT refresh, CSRF protection, and organization-scoped roles.
- Team invitations, member administration, and workspace audit logs.
- Live SAM.gov federal opportunity search with automatic recent-data loading, filters, pagination, persistence, CSV export, and pipeline actions.
- Live Grants.gov opportunity search with automatic current-data loading.
- USAspending award search and stored award intelligence.
- OpenAI Responses API integration through the Django backend.
- Grounded ForgeGov AI context from recent opportunities, awards, pipeline items, pursuits, tasks, contacts, and file metadata.
- Organization-isolated pipelines, pursuits, tasks, saved searches, contacts, contact groups, teaming records, and file metadata.
- Docker development environment and production Docker targets.

## Install this update

The installer preserves `.git` and `.env`, creates a timestamped backup, adds any missing non-secret OpenAI settings, rebuilds Docker services, and recreates the containers so current `.env` values are loaded.

```bash
cd ~/Downloads/forgegov-v1.0.2
chmod +x INSTALL.command VERIFY.command
./INSTALL.command
```

Open:

- ForgeGov: `http://localhost:3000`
- ForgeGov AI: `http://localhost:3000/assistant`
- Federal opportunities: `http://localhost:3000/opportunities/federal-contracts`
- Federal grants: `http://localhost:3000/opportunities/federal-grants`
- API health: `http://localhost:8000/api/health/`

## Configure local secrets

The installer preserves the existing project `.env`. Verify these server-side values:

```env
SAM_GOV_API_KEY=your_real_sam_key
OPENAI_API_KEY=your_real_openai_api_key
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5-mini
DJANGO_SECRET_KEY=a-long-random-secret
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

Never place the OpenAI key in a `NEXT_PUBLIC_*` variable or frontend source file. Docker Compose reads `env_file` values when containers are created, so use `docker compose up -d --force-recreate` after changing `.env`.

## Verify the release

```bash
cd ~/Documents/GitHub/forgegov
./VERIFY.command
```

The verification script checks Django configuration, migrations, backend tests, a live SAM.gov request, a minimal live OpenAI Responses API request, frontend linting, TypeScript, the production Next.js image, and both local health endpoints.

## Manual restart after changing `.env`

```bash
cd ~/Documents/GitHub/forgegov
docker compose up -d --force-recreate backend worker beat frontend
```

## Remaining product limitations

- AI answers use the bounded ForgeGov record snapshot supplied with each request; semantic retrieval across full document contents is not implemented yet.
- File records store metadata only. Actual upload storage, malware scanning, previews, OCR, and document extraction are not implemented.
- Password recovery, email verification, MFA, billing, and workspace switching are not implemented.
- Federal forecasts, contract vehicles, and state/local connectors are not configured; those pages clearly show connector status instead of mock records.
