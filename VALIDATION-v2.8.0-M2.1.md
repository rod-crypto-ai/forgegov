# ForgeGov v2.8.0-M2.1 Validation Report

## Release
Executive Capture Intelligence

## Implemented
- New default Executive Capture tab in the SAM.gov Opportunity Workspace.
- New `/api/ai/opportunities/<source_id>/capture-assessment/` endpoint.
- Evidence-based Opportunity Health score.
- Decision-support Win Probability.
- Proposal Readiness score and evidence checklist.
- Bid / Hold / No-Bid recommendation with confidence and evidence coverage.
- Six capture-risk categories with reason and mitigation.
- Prioritized capture action queue.
- Capture timeline using SAM.gov dates and indexed document date candidates.
- Capability-fit scoring using organization profile NAICS/PSC/capability signals.
- Pricing-readiness scoring using pipeline state and estimated value.
- Past-performance evidence scoring using stored award history.
- Competition posture using historical award overlap, clearly labeled as non-official bidder intelligence.
- Optional ForgeAI executive brief generation with cached `OpportunityAnalysis` records.
- Responsive Executive Capture UI for desktop, laptop, tablet/iPad, and mobile breakpoints.
- No new database migration required; latest remains `0017_award_ingestion_connector_sdk`.

## Important scoring boundaries
- Win probability is decision support, not a guaranteed outcome.
- Competition posture is inferred from historical awards and is not an official bidder list.
- Missing evidence lowers scores/confidence instead of being invented.
- Capture scoring is not legal/compliance advice.

## Static validation completed
- Modified backend Python files compile successfully.
- Python AST parsing passed.
- New backend route exists.
- Health version updated to `2.8.0-m2.1`.
- `package.json` and root `package-lock.json` aligned to `2.8.0-m2.1`.
- Modified TSX files passed TypeScript syntax transpilation.
- No `0018` migration exists.
- Full ESLint could not run in the packaging runtime because the ESLint executable is unavailable there.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py check`
4. `python manage.py test core --verbosity 2`
5. `npm run lint`
6. `npx tsc --noEmit`
7. `npm run build`
8. Manual Executive Capture tests on desktop, iPad portrait/landscape, and phone.
