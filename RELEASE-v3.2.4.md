# ForgeGov v3.2.4 — Market & Competitor Intelligence 2.0

## Release purpose

Turn ForgeGov's existing award, agency, vendor, contract-vehicle, and company-network data into one evidence-controlled market-intelligence workspace without pulling v3.2.5 pipeline automation or v3.2.6 ForgeAI platform work forward.

## Included scope

- Unified competitor dossiers and bounded two-to-four vendor comparisons.
- Agency buying-pattern trends, concentration, offices, vendors, categories, and active opportunities.
- Evidence-weighted incumbent candidates using agency, NAICS, PSC, description, current performance period, and predecessor/parent-award signals.
- Stored contract-vehicle holder, agency, obligation, ceiling, and expiration analysis.
- NAICS/PSC market maps connecting agencies, vendors, categories, and historical obligations.
- Organization-aware teaming recommendations that exclude the current company and display relationship state, supporting evidence, and gaps requiring validation.
- Strict organization scoping for private vendor CRM contacts.
- Query indexes for award, contact, and teaming analysis paths.
- Explicit official, stored, ForgeGov-derived, incomplete, and unverified evidence labels.

## Explicit exclusions

- No capture pipeline redesign, stage automation, or portfolio workflow expansion assigned to v3.2.5.
- No new autonomous or generative ForgeAI platform features assigned to v3.2.6.
- No representation of historical vendors as confirmed current bidders or confirmed incumbents.
- No destructive vendor-record merge or production-data rewrite.

## Migration

Migration `0038_v324_market_intelligence_indexes` adds indexes only. It does not delete, merge, or rewrite user or government-source records.

## Security

- All endpoints require authentication.
- Private CRM contacts are restricted to the active organization.
- Teaming recommendations exclude the active organization.
- Public government records remain separate from tenant-owned CRM and workflow records.

## Release gate

Full Django regression, v3.2.4 targeted tests, migrations, lint, type-check, production build, cross-browser responsive QA, security/dependency scans, non-root runtime checks, backup/restore, and production health/readiness must pass before release.
