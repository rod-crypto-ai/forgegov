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

## v3.3.3 — Product-led public experience

Public landing redesign, verified-interface product tour, runtime-aware conversion, $2,000 annual offering, persisted onboarding/support inquiries, SEO, and responsive/accessibility validation. This completes a public-experience increment within the existing commercial-readiness initiative; billing/provider/legal gates remain separate.

## v3.3.5 — Platform quality and operational recovery

Stabilization within commercial readiness covers shared navigation accessibility, mobile legibility, public-page request isolation, consistent theme hydration, ForgeAI provider failure responses, frontend security updates, and USAspending repeat-ingestion efficiency and timeout recovery. Existing roadmap features retain their sequence. Release evidence must distinguish synthetic workflow validation from live-provider and payment validation.

## v3.3.6 — Saved opportunity continuity

Preserve access to saved SAM.gov pursuits when live source lookup is unavailable, with explicit stored-evidence disclosure and source verification boundaries. Correct long persisted AI-history layout and unverified configuration labels. This is a reliability correction within commercial readiness.

## v3.3.7 — Session renewal reliability

Correct expired-access-cookie and overlapping refresh-request failures while preserving refresh-token validation, CSRF, rotation, session revocation, account state, and HttpOnly cookie controls. Validate real two-tab expiry recovery in the isolated browser/backend suite.

## v3.3.8 — recover interrupted session verification

Distinguish connection errors from confirmed unauthorized sessions; keep private content gated and provide a retry screen. Preserve all server authentication and subscription rules.
