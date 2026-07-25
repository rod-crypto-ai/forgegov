# ForgeGov v0.5 — Live Award Intelligence

## What changed

- Replaced the dashboard with a new command-center experience.
- Added a live USAspending award search endpoint at `/api/live/usaspending/awards/`.
- Added live award filtering by keyword, agency, recipient, NAICS, and date range.
- Added optional persistence of USAspending results to PostgreSQL.
- Award persistence now also creates/updates related vendor and agency intelligence records.
- Added a dedicated USAspending Awards page with filters, KPIs, database sync feedback, source links, and CSV export.
- Updated integration status to report USAspending reachability, stored awards, and latest sync information.
- Added a Celery task for USAspending award synchronization.
- Added USAspending integration tests.

## Important

USAspending is a public API and does not require an API key. SAM.gov still requires a valid production API key in `.env`.

## Run

```bash
docker compose down
docker compose up --build --force-recreate -d
docker compose ps
```

Open `http://localhost:3000` and force-refresh with Command + Shift + R.
