# ForgeGov v3.2.3 — Opportunity Intelligence & Discovery 2.0

## Release purpose

Make opportunity discovery reliable across ForgeGov's official and supporting sources. This
release strengthens filtering, pagination, saved-search fidelity, permitted attachment access,
change awareness, deduplication, provenance, freshness, and connector verification.

## Included scope

- SAM.gov and Grants.gov normalized live opportunity search.
- Solicitation number, set-aside, NAICS, PSC, agency/office, place-of-performance, posted-date,
  response-date, and source-supported status filters.
- Saved searches that preserve the same supported live-search filters used by the UI.
- Source-ID deduplication and explicit live-source provenance timestamps.
- Existing solicitation description and attachment retrieval through permitted official APIs,
  with official-source fallback when secure preview is unavailable.
- Existing source-version history and opportunity-change alerts retained as the amendment/change
  intelligence foundation.
- One canonical connector catalog and truthful configuration, reachability, fallback, reference,
  freshness, and stored-record states.
- Health coverage for SAM.gov, Grants.gov, SBA SUBNet, federal forecasts, USAspending awards,
  USAspending vehicle data, State & Local directory status, and ForgeGov Live Web Search.

## Explicit exclusions

- No competitor dossiers, incumbent ranking expansion, agency buying-pattern analysis, market
  maps, vendor comparisons, pricing intelligence, or teaming recommendations. Those remain in
  v3.2.4 — Market & Competitor Intelligence 2.0.
- No claim that State & Local directory links form a live aggregated opportunity feed.
- No fabricated records or live/healthy labels without a current successful probe.
- No production credential, deployment, or infrastructure changes.

## Data and security

- No database migration is required. Existing connector, source-version, quarantine, opportunity,
  saved-search, and alert models are reused.
- Connector probes are authenticated and rate-limited. API keys remain server-side and probe
  failures return sanitized details.
- External calls retain bounded limits, timeouts, retry/backoff, and circuit-breaker behavior.

## Acceptance gate

- Source filters reach the documented upstream parameter names and date formats.
- Next/Previous never repeat the prior page or silently change active filters.
- Duplicate source IDs are returned once and reported as removed duplicates.
- Cached, indexed, fallback, reference-only, unverified, unavailable, and live states remain
  visibly distinct.
- Saved-search evaluation reuses the filters saved from interactive discovery.
- Connector Manager and platform operations use the same canonical connector keys and states.
- Full Django, targeted v3.2.3, frontend, browser/responsive, security, dependency, backup/restore,
  health, readiness, and container validation gates pass before commit approval.
