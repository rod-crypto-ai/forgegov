# Product Roadmap

## Active versioned sequence

1. v3.2.2 — Proposal Intelligence & Review Automation (completed)
2. v3.2.3 — Opportunity Intelligence & Discovery 2.0 (completed)
3. v3.2.4 — Market & Competitor Intelligence 2.0 (completed)
4. v3.2.5 — Capture Operations & Pipeline 2.0 (completed)
5. v3.2.6 — ForgeAI Intelligence Platform (completed)
6. v3.3.0 — Commercial Subscription & Launch Readiness (in development)

Connector reliability, source provenance, discovery filters, pagination, saved searches,
permitted attachment access, change detection, duplicate prevention, and source freshness
belong to v3.2.3. Competitor dossiers, incumbent analysis, agency buying patterns, contract
vehicle analysis, market maps, vendor comparisons, and teaming recommendations remain
assigned to v3.2.4.

v3.3.0 is limited to commercial subscription operations, customer onboarding, entitlement and
usage governance, operational launch controls, and subscription-readiness validation. It does not
reopen or reorder the completed v3.2.2–v3.2.6 feature sequence. Stripe credential activation,
remaining legal/commercial policy, and production billing remain explicit approval gates.
Howard Dynamics and Strictly Hunter retain permanent grandfathered platform access and are
excluded from subscription checkout and payment-provider state changes.

## Milestone 1 — Foundation (included here)

- Repository, Docker, CI, Django, Next.js, PostgreSQL, Redis, Celery.
- Responsive app shell and working routes.
- Core models and API endpoints.
- SAM.gov live-search connector and USAspending status connector.

## Milestone 2 — Operational MVP

- User registration, email verification, organization onboarding, invitations, and complete role enforcement.
- Scheduled SAM.gov synchronization with deduplication and source history.
- Opportunity detail pages, attachments, saved searches, alerts, and deadline tracking.
- Capture board with activity history, notes, tasks, comments, and bid/no-bid scoring.
- Company capability profile and explainable opportunity matching.

## Milestone 3 — Intelligence

- USAspending award ingestion and vendor/agency profiles.
- Contract expiration and recompete estimates.
- OpenSearch faceted search.
- AI solicitation summaries with citations and compliance extraction.

## Milestone 4 — Collaboration and revenue

- Teaming partner discovery, contacts, proposal workspace, file versioning, calendar/email integrations.
- Billing, plans, usage limits, workspace administration, and audit exports.

## Milestone 5 — Production hardening

- Security review, penetration testing, data-quality monitoring, backup restoration tests, accessibility, performance, and incident response.
