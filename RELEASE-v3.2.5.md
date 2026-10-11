# ForgeGov v3.2.5 — Capture Operations & Pipeline 2.0

## Release purpose

Turn the existing Pipeline, Pursuits, Tasks, bid-decision, pricing, and executive reporting features into one governed capture operating rhythm without pulling ForgeAI platform work from v3.2.6 forward.

## Included scope

- Canonical active-pursuit, pipeline-value, and weighted-pipeline definitions.
- Separate overdue and due-within-14-days measures.
- Pipeline aging, stale-pursuit, missing-owner, missing-next-action, and conversion-gap signals.
- Standard and accelerated reusable milestone templates.
- Ordered milestone dependencies and completion evidence.
- Governed stage transitions with bid/no-bid and capture-plan gates.
- Explicit override reasons recorded in immutable pursuit history.
- Probability and stage-change history from the existing Pursuits workspace.
- Owner workload, open-task, and overdue-task rollups.
- Agency concentration and pursuit portfolio exposure.
- One organization-scoped weekly capture review record per week.
- Responsive Capture Operations workspace at `/capture/operations`.

## Explicit exclusions

- No autonomous pursuit decisions, generated capture strategies, or new ForgeAI platform behavior assigned to v3.2.6.
- No destructive rewrite, merge, or deletion of existing pipeline, pursuit, task, pricing, proposal, or collaboration records.
- No silent stage transitions; governed actions remain attributable and reviewable.

## Migration

Migration `0039_v325_capture_operations` adds capture plans, milestones, pursuit change history, weekly review records, supporting indexes, and the previously displayed Archived pursuit stage. It preserves all existing records.

## Security

- Every capture operations request requires an active organization membership.
- Read access is organization scoped; viewers cannot mutate capture operations.
- Pursuits, milestones, reviews, workload, and history cannot cross tenant boundaries.
- Existing Financial Sensitive controls remain responsible for detailed profit, pricing, and cash-flow data.

## Release gate

Full Django regression, v3.2.5 targeted tests, migration checks, lint, type-check, production build, Chromium/Firefox/WebKit responsive QA, dependency/security scans, non-root runtime checks, backup/restore, and production health/readiness must pass before release.
