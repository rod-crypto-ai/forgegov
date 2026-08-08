# ForgeGov v2.9.0-M1 — Proposal & Compliance Command Center

## Added
- New Proposal Workspace tab inside each federal opportunity.
- New endpoint: `GET /api/ai/opportunities/<source_id>/proposal-workspace/`.
- Evidence-backed compliance matrix combining user workspace items and indexed solicitation signals.
- Proposal outline seeded from Section L, Section M, CLIN, staffing, and document evidence.
- Proposal readiness and document-evidence KPIs.
- Pink Team, Red Team, Gold Team, and final submission target dates calculated from the stored response deadline.
- Submission readiness gate.
- Proposal task rollup from the existing pipeline task system.
- Missing-evidence alerts for Sections L/M, indexed files, and expired deadlines.
- Responsive desktop, tablet/iPad, and phone layouts.
- No new database migration; existing workspace/task/document models are reused.

## Evidence boundary
ForgeGov does not invent solicitation requirements. Missing Section L/M or other evidence is shown as missing/needs review. Final instructions, amendments, evaluation factors, and submission requirements must be verified against the current official solicitation.
