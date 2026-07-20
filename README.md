# ForgeGov

ForgeGov is a government-contracting intelligence and capture-management platform built with Django, PostgreSQL, Redis, Celery, Next.js, and GitHub Actions.

## Current working foundation

- Responsive ForgeGov application shell for desktop, tablet, and mobile.
- Django REST API with JWT endpoints.
- Organization, membership, opportunity, pipeline, task, saved-search, and data-sync models.
- Live SAM.gov opportunity search with filters for title, agency, NAICS, PSC, state, set-aside, notice type, dates, and pagination.
- Optional idempotent persistence of SAM.gov search results into PostgreSQL.
- Daily SAM.gov background-sync task with retry handling and sync-run monitoring.
- Real dashboard counts from the ForgeGov database—no fabricated metrics.
- USAspending connectivity configuration.
- Docker Compose and GitHub Actions configuration.

## Secure local configuration

The SAM.gov key is a secret. It must never be committed to GitHub or placed in frontend code.

Run:

```bash
python scripts/configure_local.py
```

The script securely prompts for the key, generates a Django secret, and writes a local `.env` file. `.env` is ignored by Git.

To enable the daily SAM.gov sync after confirming the account's API rate limit, set:

```env
SAM_SYNC_ENABLED=true
```

## Start with Docker

```bash
docker compose up --build
```

Open:

- ForgeGov: `http://localhost:3000`
- API: `http://localhost:8000/api/`
- Django admin: `http://localhost:8000/admin/`

Create an administrator:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Run without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Verification

```bash
python backend/manage.py test core
ruff check backend
cd frontend && npm run lint && npm run build
```

The repository is an operational foundation, not a finished GovTribe/HigherGov replacement. Authentication UI, workspace onboarding, complete permission enforcement, alerts, award ingestion, and production search infrastructure remain on the roadmap.
