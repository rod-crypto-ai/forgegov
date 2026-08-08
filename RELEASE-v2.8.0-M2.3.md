# ForgeGov v2.8.0-M2.3 — Capture Command Center

## What changed
- New default **Command Center** tab in the federal opportunity workspace.
- New endpoint:
  - `GET /api/ai/opportunities/<source_id>/command-center/`
- Aggregates Executive Capture + Win Strategy into a single operating view.
- Opportunity Health, Win Probability, Proposal Readiness, and Bid Posture KPIs.
- Unified priority action queue.
- Proposal work list from workspace tasks and Project Room tasks.
- Capture Memory built from pipeline notes, Project Room notes, and saved ForgeAI analyses.
- Combined acquisition + capture + Project Room activity timeline.
- Risk Watch panel.
- Market + Teaming snapshot.
- Pricing-readiness snapshot.
- Existing Executive Capture and Win Strategy tabs remain available for deeper analysis.
- Responsive Command Center layouts for desktop, laptop, tablet/iPad, and phone.
- No database migration required; latest remains `0017_award_ingestion_connector_sdk`.

## Evidence boundaries
- Bid posture and win probability remain decision-support signals, not guaranteed outcomes.
- Incumbent and likely-competitor signals remain clearly derived unless confirmed by official evidence.
- Capture Memory only uses information already stored inside the authorized ForgeGov workspace.
