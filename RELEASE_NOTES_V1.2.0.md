# ForgeGov v1.2.0 — Intelligence Expansion

## Added

- SAM.gov opportunity detail pages with protected-description retrieval, public document links, and direct pipeline actions.
- Acquisition.gov federal procurement forecast directory with live source refresh and fallback behavior.
- USAspending federal contract-vehicle explorer using IDV award types and optional persistence.
- SBA SUBNet current subcontracting opportunity search.
- SAM.gov Acquisition Subaward Reporting search for prime/subcontract performance intelligence.
- Federal agency buyer profiles with spend, award count, active opportunities, top vendors, top NAICS, recent awards, and recent opportunities.
- Vendor and competitor profiles with spend, award history, agency concentration, and NAICS strengths.
- Teaming-partner discovery using vendor, NAICS, socioeconomic, location, and award indicators, with one-click creation of draft teaming leads.
- Opportunity-level incumbent signals inferred from matching stored award history, clearly labeled as candidates rather than confirmed incumbents.
- NAICS and PSC market analytics combining stored award and opportunity data.
- Saved-search alert evaluation, alert deduplication, organization isolation, inbox, read/unread state, and dismissal.
- State and local procurement source directory with verified public portals and a national NASPO directory entry.
- Render Celery beat service for scheduled alert evaluation.

## Data sources

- SAM.gov Contract Opportunities Public API
- SAM.gov Contract Awards API
- SAM.gov Acquisition Subaward Reporting Public API
- USAspending API
- Acquisition.gov Agency Procurement Forecast Directory
- U.S. Small Business Administration SUBNet
- Grants.gov API

## Deployment notes

Run migrations before application startup. Render deployments should provision both `forgegov-worker` and `forgegov-beat`. The worker and beat services require the same `SAM_GOV_API_KEY`, database, Redis, and Django secret configuration as the API service.

## Known boundaries

Federal forecast records and state/local solicitations are published in inconsistent formats across agencies and jurisdictions. v1.2.0 provides verified directories and connector-ready interfaces; normalized record ingestion must be added source by source where a stable public API or machine-readable feed exists.
