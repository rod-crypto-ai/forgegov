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
| UX-01 | High | Dashboard signal/deadline/activity cards force 390px height regardless of content; empty cards waste space while activity has an inner scrollbar. CSS fixed height/min/max height. | Open |
| UX-02 | High | Federal search filter labels touch the panel's upper border. Generic `.data-panel` has no default content padding and structured children disagree about ownership. | Open |
| UX-03 | Medium | Federal search action buttons stretch to a full grid row and large headings dominate the available workspace. | Open |
| DATA-01 | High | Dashboard reports award sync `failed` with zero awards refreshed in 30 days despite 13,232 stored records. Current SAM.gov search returns results. Provider failure must not be represented as live award freshness. | Ingestion failure remains under investigation. Live connector probe succeeded for all seven machine-readable sources; state/local correctly reports reference-only. |
| UX-04 | High | Federal feed source switch visibly renders old SAM rows as blank USAspending awards. The response is not tied to the selected source and older requests can overwrite newer responses. | Source guards and request ordering implemented; browser regression pending. |
| UX-05 | High | Tasks and saved searches show blank content without loading/empty guidance. Task completion/deletion and saved-search deletion reject without user-facing errors. | Loading/empty states, accessible action labels, busy guards and mutation error handling implemented; browser regression pending. |
| UX-06 | High | Pursuit stage movement updates the screen before saving; a rejected request leaves the card in the unsaved stage. | Stage display now changes only after a successful server response; regression pending. |
| UX-07 | Medium | Legacy CSS uses undefined surface/foreground/background/input variables across network, room, and newer components. This breaks backgrounds and theme consistency. | Semantic aliases and shared dark dashboard colors implemented; browser regression pending. |

## Coverage ledger

Production checked: landing, sign-in, dashboard, federal contract search. Remaining routes and
workflow checks are pending; source review and fixture tests alone do not establish live-data health.

## Verification results

Local full Django regression: 364/364 passed on 2026-10-22. Lint and typecheck passed for
the initial shared CSS/feed changes; final rerun and production build are pending the complete stage.
Local browser binaries could not be downloaded (gateway/download errors); the cloud browser
cannot reach the local Next.js server. GitHub responsive QA will produce screenshots and
JSON evidence for review. Production browser access remains available.
