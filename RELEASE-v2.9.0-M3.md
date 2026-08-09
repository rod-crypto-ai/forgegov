# ForgeGov v2.9.0-M3 — Submission Control, Executive Exports & Proposal Closeout

## What changed
- Added a new Submission Control tab to federal opportunity workspaces.
- Added immutable, SHA-256 hashed submission snapshots that preserve:
  - opportunity state
  - requirement/compliance state
  - review-gate state
  - review findings
  - final file manifest
  - amendment baseline
  - delivery method
  - confirmation reference
  - submission notes
- Submission recording is blocked until M2 human gates are clear.
- Added proposal closeout lifecycle:
  - submitted
  - evaluation
  - discussions
  - final proposal revision
  - awarded
  - lost
  - cancelled
- Added awardee, award value/date, debrief tracking, win/loss reason, customer feedback, strengths, weaknesses, and lessons learned.
- Added executive exports:
  - Executive Opportunity Brief PDF
  - Compliance Matrix XLSX
  - Management Summary PowerPoint
- Added amendment protection through the existing M2 amendment baseline/readiness gate.
- Added persistent submission history with receipt/reference and snapshot hash.
- Added migration `0019_submission_control_closeout.py`.
- Added `reportlab` and `python-pptx` backend dependencies for native export generation.

## New API routes
- `GET/POST /api/ai/opportunities/<source_id>/submission-control/`
- `GET /api/ai/opportunities/<source_id>/submission-exports/<format>/`

## Important boundary
ForgeGov records and preserves internal submission evidence; it does not submit proposals to SAM.gov or another agency portal and does not replace the official portal receipt.
