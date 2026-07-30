# ForgeGov v2.0 — Integrated Workspace

## Major changes

- Global search across indexed opportunities, vendors, agencies, and awards.
- Contextual search results open the relevant ForgeGov profile or workspace.
- Federal opportunity detail workspace now includes an internal document viewer.
- Original SAM.gov attachment filenames are preserved.
- Unsupported document formats use an explicit source fallback rather than silently navigating away.
- Context-aware ForgeGov AI is embedded in each federal opportunity and grounded in the open record.
- Incumbent signals link directly to unified vendor profiles.
- Vendor intelligence now includes website, NAICS, related opportunities, contract vehicles, contacts, and recent award intelligence where stored.
- Pipeline lifecycle now includes an Archived stage in addition to permanent deletion.
- Teaming statuses match backend lifecycle values, with Closed presented as Archived.
- Forecast sources use a ForgeGov activity-feed presentation and internal review overlay.
- Contract vehicle, awards, reported performance, and teaming records remain connected to company profiles.
- SBA SUBNet pagination and full-page navigation from v1.3.0 are retained.

## Source boundaries

Some external federal and agency sites prohibit iframe embedding through browser security headers. ForgeGov previews supported documents internally and clearly labels the official-source fallback when secure embedding is unavailable.

## Validation

- Python source compiled successfully with `python -m compileall`.
- Django runtime validation could not run because Django is not installed in the build container.
- Next.js dependency installation was blocked by the container registry returning 404 for `zod-validation-error@4.0.2`; run `npm ci && npm run build` in the deployment environment.
