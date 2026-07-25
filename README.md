# ForgeGov

ForgeGov is a government-contracting intelligence and capture-management platform built with Django, PostgreSQL, Redis, Celery, Next.js, and GitHub Actions.

## ForgeGov v0.3 foundation

The application now follows the deeper product structure shown in the GovTribe reference screenshots while retaining original ForgeGov branding and interface design.

### Navigation and workspace modules

- ForgeGov AI.
- Capture: dashboard, teaming, pipelines, pursuits, tasks, and saved searches.
- Beacon: contacts and contact groups.
- Reports: funding and new entrants.
- Opportunities: federal forecasts, federal contracts, federal contract vehicles, state/local contracts, and federal grants.
- Awards: federal contracts, IDVs, contract vehicles, grants, state/local contracts, state/local IDVs, and state/local vehicles.
- Participants: federal agencies, states, jurisdictions, and vendors.
- Files: government files and user files.
- Categories: NAICS, PSC, NIGP, and UNSPSC.
- Workspace and settings.

### Operational functionality

- Responsive, collapsible desktop and mobile navigation.
- Live SAM.gov opportunity search through the Django backend.
- Advanced opportunity filters, result persistence, CSV export, and source links.
- Real dashboard metrics from the database—no fabricated totals.
- API-backed tables with search, filtering controls, refresh, and CSV export.
- Django CRUD endpoints for pursuits, awards, agencies, vendors, contacts, contact groups, teaming requests, files, participants, and categories.
- Expanded capture, buyer, vendor, award, file, and classification data models.
- AI workspace prepared for a grounded model connection; it explicitly refuses to invent results while no model service is configured.
- Docker Compose and GitHub Actions configuration.

## Secure local configuration

The SAM.gov key is a secret. It must never be committed to GitHub or placed in frontend code.

```bash
python3 scripts/configure_local.py
```

The script securely prompts for the key, generates a Django secret, and writes a local `.env` file. `.env` is ignored by Git.

## Start with Docker

```bash
docker compose up --build -d
docker compose ps
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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend, in another Terminal window:

```bash
cd frontend
npm install
npm run dev
```

## Verification performed for v0.3

```bash
python manage.py test
ruff check .
npm run lint
npm run build
```

- Five Django tests passed.
- Django system checks passed.
- Ruff passed.
- ESLint passed.
- Next.js production build passed.
- Home, opportunity, and contact routes returned HTTP 200 in a local production-server check.

## Honest product status

This is now a substantially broader application foundation, but it is not yet a finished GovTribe or HigherGov replacement. A complete commercial platform still requires organization-scoped authorization, onboarding, working create/edit forms for every module, award ingestion, Grants.gov ingestion, state/local data licensing and connectors, document storage and extraction, a grounded AI service, alerts, email delivery, payment plans, and production deployment hardening.
