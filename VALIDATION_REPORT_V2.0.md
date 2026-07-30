# ForgeGov v2.0 Validation Report

## Passed
- Python syntax compilation for backend/core and backend/forgegov.
- URL import/source inspection for the global intelligence search endpoint.
- Source-level review of opportunity detail, global search, forecast feed, pipeline lifecycle, teaming lifecycle, and vendor intelligence changes.

## Deployment checks required
1. `cd frontend && npm ci && npm run build`
2. `cd backend && pip install -r requirements.txt`
3. `python manage.py check`
4. `python manage.py migrate`
5. Smoke-test SAM.gov detail documents, OpenAI contextual answers, USAspending profiles, SBA pagination, and forecast source links.

The package does not claim that external sites permitting no iframe embedding can be forced to render inside ForgeGov. The UI provides an internal workspace and explicit fallback for those sources.
