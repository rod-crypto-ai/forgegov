# ForgeGov v2.9.0-M2 — Proposal Execution & Review Management

## What changed
- Added persistent Proposal Plan state per company workspace + opportunity.
- Added persistent Proposal Requirements with:
  - human-controlled compliance status
  - owner assignment
  - due date
  - notes
  - evidence/source linkage
- Added persistent Pink, Red, Gold, and Final review gates.
- Added persistent review findings with severity, owner, due date, and disposition.
- Added human-controlled final submission verification.
- Added Submission Readiness scoring that is blocked by:
  - unresolved requirements
  - incomplete review gates
  - open findings
  - unreviewed solicitation changes
  - missing final submission verification
- Added solicitation/amendment baseline tracking using:
  - official modified timestamp
  - response deadline
  - resource links
  - indexed document checksums
- Added “Mark reviewed” amendment-baseline workflow.
- Added Project Room proposal-task rollup inside Proposal Execution.
- Added company member assignment options for requirements and reviews.
- Added new Proposal Execution tab to the federal opportunity workspace.
- Preserved M1 Proposal Workspace for planning; M2 handles persistent execution.
- Tightened Proposal Workspace document queries to the active organization.
- Added migration `0018_proposal_execution_review_management.py`.

## New API routes
- GET/POST `/api/ai/opportunities/<source_id>/proposal-execution/`
- PATCH `/api/ai/opportunities/<source_id>/proposal-requirements/<requirement_id>/`
- PATCH `/api/ai/opportunities/<source_id>/proposal-reviews/<review_id>/`
- PATCH `/api/ai/opportunities/<source_id>/proposal-findings/<finding_id>/`

## Important boundary
ForgeGov does not automatically certify a requirement as compliant. A human user must set compliance status and verify the current official solicitation, amendments, evaluation criteria, and submission instructions.
