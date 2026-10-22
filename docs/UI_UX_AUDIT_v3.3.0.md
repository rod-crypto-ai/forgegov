# ForgeGov v3.3.0 experience audit

Status: in progress. This is a launch-readiness correction pass, not a new roadmap release.

## Baseline and safeguards

- Started 2026-10-22 from clean commit `669fac6274b1ff9b6bc3b2b9c248e0fcecc56e7c`.
- Remote main and commercial-readiness branch match that revision.
- Working branch: `stabilization/v3.3.0-experience-audit`.
- Production browser sign-in verified as workspace owner. Production inspection is read-only;
  workflow mutations run against isolated test data.
- Preserve tenant permissions, official branding, customer records, and permanent billing
  exemptions for Howard Dynamics and Strictly Hunter. No production billing activation.
- Keep the deployed revision as the rollback baseline. Deployment is gated on validation.

## Ordered correction plan

1. Inspect all navigation routes and public/authentication surfaces; record actual failures,
   loading/error/empty states, provenance, and representative screenshots.
2. Correct shared panel spacing, heading hierarchy, controls, responsive layouts, and theme
   tokens. Recheck nested panels and table/filter containers to avoid double padding.
3. Exercise discovery, source feeds, awards, forecasts, subcontracting, capture, Project Rooms,
   company/network, reports, ForgeAI, settings/security, and billing. Correct existing defects.
4. Run local browser regression at phone, tablet, laptop, and desktop sizes in both themes;
   run integration/backend regression, lint, typecheck, build, and cross-browser suites.
5. Commit and push verified stages, inspect CI, and document remaining release gates honestly.

## Findings verified on the deployed site

| ID | Priority | Evidence and cause | State |
| --- | --- | --- | --- |
| UX-01 | High | Dashboard signal/deadline/activity cards force 390px height regardless of content; empty cards waste space while activity has an inner scrollbar. CSS fixed height/min/max height. | Corrected; stage-1 screenshot and 30-case regression verified. |
| UX-02 | High | Federal search filter labels touch the panel's upper border. Generic `.data-panel` has no default content padding and structured children disagree about ownership. | Shared inset corrected; stage-1 geometry/screenshots verified. |
| UX-03 | Medium | Federal search action buttons stretch to a full grid row and large headings dominate the available workspace. | Shared control alignment and heading scale corrected; stage-1 browser verified. |
| DATA-01 | High | Dashboard reports award sync `failed` with zero awards refreshed in 30 days despite 13,232 stored records. Current SAM.gov search returns results. Provider failure must not be represented as live award freshness. | Ingestion failure remains under investigation. Live connector probe succeeded for all seven machine-readable sources; state/local correctly reports reference-only. |
| UX-04 | High | Federal feed source switch visibly renders old SAM rows as blank USAspending awards. The response is not tied to the selected source and older requests can overwrite newer responses. | Stage-1 out-of-order and failed-switch regression passed in all 30 cases. |
| UX-05 | High | Tasks and saved searches show blank content without loading/empty guidance. Task completion/deletion and saved-search deletion reject without user-facing errors. | States and mutation handling corrected; expanded interactive checks in stage 2. |
| UX-06 | High | Pursuit stage movement updates the screen before saving; a rejected request leaves the card in the unsaved stage. | Server-confirmed stage change implemented; failed/successful transition test added in stage 3. |
| UX-07 | Medium | Legacy CSS uses undefined surface/foreground/background/input variables across network, room, and newer components. This breaks backgrounds and theme consistency. | Semantic aliases and shared dark dashboard colors implemented; browser regression pending. |

## Coverage ledger

Production inspected: landing/sign-in; dashboard; federal opportunity search and recent activity;
connectors; capture operations, pipelines, pursuits, tasks, saved searches, alerts and teaming;
Project Rooms; company/network/contacts; executive, funding and new-entrant reports; forecasts,
vehicles, subcontracting, state/local sources and grants; award intelligence and federal awards;
vendor/agency research, categories/NAICS; settings, account, security, billing, workspace,
notifications and audit log. A route visit is not an end-to-end workflow pass. Production writes
to customer workspaces, authentication policy and billing have deliberately not been exercised.
ForgeAI responses, document/pricing/proposal workflows, public recovery flows, detailed opportunity
tabs, and complete large-result pagination still require focused interactive verification.

## Stage 1 evidence — commit b8627a3

All four CI jobs passed in run 39775801893: backend, frontend, Docker release QA and responsive
release QA. The four existing browser suites passed 21 cases each. The added experience suite
passed 30 cases: Chromium/Firefox/WebKit, five viewport sizes (390–1920px), light/dark themes.
Evidence artifact: `responsive-experience-evidence` (14-day CI retention).

UX-01 through UX-06 have automated regression coverage and stage-1 browser evidence. Dashboard
empty-card heights are content-sized (110–201px on phones), document overflow is zero, and feed
control insets are 15px on phones / 25px on desktop. Screenshots were manually reviewed: shared
padding improved, but dark shortcut backgrounds and metric text still failed visual review despite
passing structural assertions. Stage 2 corrects those tokens and expands the dark-theme assertions.
UX-07 therefore remains partially verified until the second-stage evidence is reviewed.

## Stage 2 corrections — CI verified (aac8fe3)

- Company invitation inputs had no reusable dimensions/border treatment. Shared form controls now
  inherit consistent 42px minimum height, padding, focus styling and theme tokens.
- Funding and New Entrants routes displayed a generic private-pipeline report. They now use an
  authenticated, read-only stored-public-award report endpoint with agency/NAICS filters, pagination,
  current-page CSV export and meaningful loading/error/empty states. Entrants are grouped over all
  available stored history *before* applying the first-observed date window. Coverage limitations
  explicitly prevent presenting first-observed relationships as proof of new market entrants.
- Read-only production aggregates found 13,232 stored awards with zero NAICS, PSC or source update
  values. The importer requested undocumented field names and defaulted to award-ID sorting. It now
  requests documented `NAICS`, `PSC`, `Last Modified Date` fields, extracts nested category codes,
  sorts by last modification, and preserves existing known values when a partial record omits them.
  Primary references: USAspending API `spending_by_award.md` contract and corresponding v2 view in
  https://github.com/fedspendingtransparency/usaspending-api. This does not repair existing production
  history until a separately approved, bounded ingestion is completed and checked.
- Dashboard wording distinguishes stored notices, source dates and last sync attempts; live award
  search explains historical source evidence. Removed stale account/settings version text and
  implementation-oriented customer copy. Added accessible workspace view-toggle state.
- Six backend tests cover report authorization, parameters, historical entrant exclusion, funding
  totals/filtering, empty/paginated results, official nested category fields and partial-record safety.
- Browser regression expanded to task creation/timezone conversion and failed mutations, saved-search
  empty guidance, report rendering/pagination/CSV, company control geometry and dark shortcut surfaces.
  All 30 expanded cases passed in CI run 39778500757; backend/frontend/Docker jobs also passed.
  Screenshots of dark phone dashboard, desktop funding, phone entrants and dark company were reviewed.
  Remaining company summary contrast and mobile sticky pagination defects led directly to stage 4.

## Open release gates

- Award ingestion has recently failed to reach USAspending, although connector probes succeeded.
  Network/provider recovery and classification backfill must be verified independently of field fixes.
- Forecast/state-local directories are not live notices. Forecast directory labels corrected in
  stage 4; continue verifying source availability independently of directory coverage.
- Generic IDV/vehicle result interactions and large-result pagination still need follow-up.
- Full workflow, accessibility and visual coverage remains incomplete. Do not mark the audit complete
  or approve commercial release solely because fixture-driven CI passes.
- No production deployment, merge, release tag, billing activation or customer-data migration in this pass.
- Public Terms of Use and Privacy Notice still explicitly identify themselves as operational private-beta
  drafts pending qualified-counsel review. Do not rewrite this into a claim of legal approval.

## Verification results

Local full Django regression: 370/370 passed on 2026-10-22 after stage 2. Lint, typecheck,
production build, migration consistency, fatal-error lint, source audit and diff checks passed.
Local browser binaries could not be downloaded (gateway/download errors); the cloud browser
cannot reach the local Next.js server. GitHub responsive QA will produce screenshots and
JSON evidence for review. Production browser access remains available.

## Stage 3 corrections — CI verified (3c43e5a)

- Pursuit board now retains Lost, No Bid and Archived lanes. A rejected stage save does not move
  the card; mutation controls disable while saving. Native modal dialogs provide keyboard focus
  containment and Escape dismissal, with an accessible opening button. Local date/time inputs
  now convert correctly to UTC rather than silently treating displayed UTC as local time.
- Project Rooms now distinguishes loading, empty, error and created states. Creation trims input,
  blocks duplicate submission, preserves a success message and offers recovery on errors.
- Audit log displays its actual latest-250-event scope, 25-event pages, a labelled loaded-event
  filter, loading/error/empty states and responsive date/actor rows. No server permission changes.
- Browser fixtures exercise failed and successful pursuit transitions, modal date display/Escape,
  room creation, audit pagination/filtering and overflow at every tested viewport/theme/engine.
- Production session expired during the audit. Existing authenticated observations remain valid,
  but remaining live authenticated workflow tests require reauthentication; do not infer results
  from fixtures or change customer preferences merely to test themes.

## Stage 4 visual evidence follow-up — CI verified (d6b9331)

- Stage-2 screenshots exposed sticky pagination overlaying report metrics on phones. Pagination now
  stays in document flow; extra mobile bottom clearance keeps fixed feedback access off final content.
- Company summary cards inherit theme surfaces, profile checkboxes align inline with their labels,
  and adjacent company panels no longer stretch to an empty tall column. Team/invitation lists have
  explicit empty guidance. The summary theme fix was introduced in stage 3.
- Forecast cards no longer fabricate Active/event status or a Feed label from directory references.
  They say Directory reference / source and the drawer explicitly states it is not a live notice.
  Searches are labelled, empty/loading states are explicit, and request sequencing rejects stale results.
- Added browser assertions for in-flow pagination, dark company surfaces, invitation guidance and
  fallback directory labels/source details. Fixture snapshots are not proof of live forecast notices.

Stage 3 run 39779226543 and stage 4 run 39780021931 passed all four CI jobs. Stage-4
artifact 12428345144 contains 30 passing experience cases plus the existing release suites.
Screenshots confirmed pagination in document flow and readable dark company cards. They also
exposed remaining white room-summary/status surfaces, addressed below. Browser sign-in was
renewed successfully as the existing workspace owner; no account/security policy was changed.

## Stage 5 — source-aware navigation and award-result completion

- Live global search for `maintenance` returned actual opportunity, pursuit, company, vendor and
  award matches. Clicking the Keystone Job Corps SBA SUBNet result reproduced a wrong-source
  failure: the result pointed to a SAM-only details route. The actual subcontract route loaded the
  listing, dates, source provenance and all four research/capture/collaboration tabs correctly.
- Search opportunity/document links and pipeline links now distinguish SAM, Grants.gov and SBA
  SUBNet destinations. Backend tests check all three source routes and invalid search-limit handling.
- Generic IDV/vehicle tables previously fetched only offset zero and offered no record detail.
  They now expose source-reported total counts, Previous/Next offset pagination and expandable
  normalized record details. Table/board/export views remain available. Filters/exports explicitly
  apply to the loaded page; historical signing dates are not described as retrieval freshness.
- Late responses are rejected and route-keyed workspaces reset page state. Spreadsheet-formula
  prefixes are neutralized in generic CSV exports while numeric values remain numeric.
- Dark room summaries, status pills and inline messages now use semantic theme surfaces/text.
  Browser assertions cover those surfaces, IDV/vehicle pagination, route resets, details and CSV safety.
- ForgeAI rendered its configured-provider/research controls; no generated-answer claim is made.
  Live generation and pricing/proposal mutations still require controlled workflow validation.
