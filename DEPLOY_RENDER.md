# Deploy ForgeGov v1.2.0 on Render

ForgeGov includes a root-level `render.yaml` Blueprint for the Next.js frontend, Django API, PostgreSQL, Render Key Value, Celery worker, and Celery beat scheduler.

## Before deployment

1. Install and verify v1.2.0 locally with `./ROLLOUT_V1.2.0.command`.
2. Commit the verified files to the GitHub repository.
3. Push the `main` branch.
4. Confirm `.env`, API keys, Celery schedule files, `.next`, and `node_modules` are not committed.

## Create or sync the Blueprint

1. Open Render and choose **New → Blueprint**.
2. Select the ForgeGov GitHub repository and `main` branch.
3. Render detects `render.yaml` at the repository root.
4. Supply the two secret values when prompted:
   - `SAM_GOV_API_KEY`
   - `OPENAI_API_KEY`
5. Apply the Blueprint.

The Blueprint provisions:

- `forgegov` — Next.js frontend
- `forgegov-api` — Django API
- `forgegov-worker` — Celery worker
- `forgegov-beat` — scheduled saved-search alert evaluation
- `forgegov-db` — PostgreSQL
- `forgegov-redis` — Render Key Value / Redis-compatible queue and cache

## Deployment acceptance checks

After all services are live:

1. Open `https://forgegov.onrender.com`.
2. Open `https://forgegov-api.onrender.com/api/health/` and confirm version `1.2.0`.
3. Register or sign in.
4. Search Federal Contract Opportunities and open **Details & files**.
5. Test Federal Forecasts, Contract Vehicles, Subcontracting, Teaming, Agency Profiles, Vendor Profiles, NAICS/PSC Analytics, and Alerts.
6. Check the API, worker, and beat logs for migration, CORS, CSRF, authentication, or external-source errors.

## Custom domain variables

When moving from Render subdomains to custom domains, update:

Backend:

```env
DJANGO_ALLOWED_HOSTS=api.yourdomain.com
FRONTEND_URL=https://yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

Frontend:

```env
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com/api
```

Redeploy the frontend after changing `NEXT_PUBLIC_API_BASE_URL`, because Next.js embeds public environment variables during its production build.
