# ForgeGov v3.0.1 — Workspace Consolidation

## Opportunity workflow
The federal opportunity workspace is consolidated into one ordered pursuit flow:

1. Overview
2. ForgeGov AI
3. Intelligence
4. Executive Capture
5. Go / No-Go
6. Win Strategy
7. Compliance
8. Pricing
9. Proposal
10. Reviews
11. Submission
12. Timeline

Redundant Command Center, Proposal Workspace/Execution naming, standalone Capture Notes, and Submission Control tab labels are removed from the user-facing rail. Existing backend capabilities remain intact.

## Overview command page
Overview now provides cross-module pursuit state for pipeline, Go/No-Go, pricing, compliance, proposal readiness, and indexed document evidence, plus direct next actions.

## Capture consolidation
Executive Capture now contains the evidence-based capture assessment plus the persistent capture summary, working notes, risk register, and team posture in one workspace.

## API
- `GET /api/workflow/opportunities/<notice_id>/command-summary/`

This is a consolidation release: no schema migration is required.
