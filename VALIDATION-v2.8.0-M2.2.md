# ForgeGov v2.8.0-M2.2 Validation Report

## Release
Competition & Win Strategy

## Implemented
- Dedicated Win Strategy tab inside the SAM.gov Opportunity Workspace.
- New `GET /api/ai/opportunities/<source_id>/win-strategy/` endpoint.
- Similar-contract matching using official historical award evidence across agency, NAICS, PSC, and scope terms.
- Likely incumbent signal with explicit confidence and predecessor-verification warning.
- Likely competitor ranking from similar historical awards, clearly labeled as inference and never as an official bidder list.
- ForgeGov Network teaming recommendations using NAICS, PSC, certification/capability evidence, profile verification, and existing partnership state.
- Initial compliance matrix generated from indexed Section L/M, FAR/DFARS, security/certification, and deliverable signals.
- Pricing-readiness scoring based on evidence needed to create a price; no fabricated pricing estimate.
- Evidence-backed strengths, gaps, potential discriminators, and customer/evaluation hypotheses.
- Prioritized competition, compliance, pricing, incumbent, and teaming actions.
- Responsive Competition/Teaming/Compliance/Similar Contract cards for desktop, laptop, tablet/iPad, and mobile.
- No new database migration required. Latest remains `0017_award_ingestion_connector_sdk`.

## Intelligence boundaries
- Incumbent is labeled `likely` until predecessor evidence is independently verified.
- Competitors are inferred from historical awards and are not known bidders.
- Teaming recommendations are matches, not endorsements or guarantees of availability.
- Pricing readiness is evidence completeness, not a proposed price or price-reasonableness determination.
- Customer/evaluation priorities remain hypotheses unless official evidence supports them.

## Static validation completed
- Modified backend Python files compile successfully.
- Python AST parsing passed.
- New API route/import assertions passed.
- Version aligned to `2.8.0-m2.2` in backend and frontend manifests.
- No `0018` migration exists.
- Modified TSX files reached only expected missing-dependency/module errors in this packaging runtime; no TypeScript/JSX parsing errors were observed.
- Full ESLint was unavailable because project node modules are not installed in the packaging runtime.
- Django runtime checks could not execute because Django is unavailable in the packaging runtime.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py check`
4. `python manage.py test core --verbosity 2`
5. `npm run lint`
6. `npx tsc --noEmit`
7. `npm run build`
8. Manual Win Strategy testing on desktop, iPad portrait/landscape, and phone.
