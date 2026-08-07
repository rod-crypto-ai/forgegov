# ForgeGov v2.8.0-M2.1 — Executive Capture Intelligence

## What changed

- Adds the Executive Capture tab as the default SAM opportunity workspace view.
- Adds a new evidence-based capture assessment API.
- Calculates Opportunity Health, Win Probability, Proposal Readiness, capability fit, document coverage, compliance, schedule, pricing, competition posture, and past-performance evidence scores.
- Adds Bid / Hold / No-Bid decision support with confidence and evidence coverage.
- Adds six-category capture risk analysis with reasons and mitigations.
- Adds proposal-readiness checklist generated from indexed solicitation evidence and pipeline state.
- Adds prioritized next-action queue.
- Adds capture timeline combining official SAM dates with extracted document date signals.
- Adds optional ForgeAI executive briefing refresh while retaining deterministic scoring when the AI provider is unavailable.
- Uses the existing OpportunityAnalysis cache for ForgeAI capture briefs; no new database schema is required.
- Adds responsive executive capture cards for desktop, laptop, iPad/tablet, and phone widths.

## Evidence and safety

- Win probability is decision support, not a guaranteed outcome.
- Competition posture uses historical award overlap and is not an official bidder list.
- Missing evidence lowers readiness/confidence rather than being invented.

## Database

No new migration. Latest migration remains `0017_award_ingestion_connector_sdk`.
