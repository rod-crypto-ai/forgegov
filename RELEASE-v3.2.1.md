# ForgeGov v3.2.1 — Proposal Automation & Submission Workspace + Production Live Web

## Release goal

Turn ForgeGov's existing compliance matrix, proposal reviews, submission controls, Capture Copilot, and document intelligence into a production-oriented proposal workspace while completing the production Live Web architecture that was previously deferred.

Proposal automation remains the primary release scope. Production Live Web is included as a supporting platform infrastructure workstream because proposal research, ForgeAI, Capture Copilot, and source discovery all depend on a reliable shared research service.

## Proposal Automation & Production Workspace

- Structured response volumes and sections layered onto the existing `ProposalPlan`.
- Default Technical/Management, Past Performance, and Pricing volume structure.
- Section ownership, status, instructions, due dates, approval/lock state, and controlled revision history.
- Compliance-requirement traceability with explicit link/unlink controls.
- Evidence-grounded ForgeAI section drafting using indexed solicitation chunks, linked requirements, and approved company content.
- `[VALIDATION REQUIRED]` guardrail when available evidence cannot support a claim.
- Reusable proposal-content library with draft/approved/retired lifecycle.
- Approved reusable content automatically loses approval after substantive edits unless an authorized approver explicitly re-approves the new version.
- Package validation combines section completion, compliance status, review gates, findings, and final submission-method verification before submission control.

## Proposal governance and pricing protection

- Proposal writers can draft and revise content but only Owner/Admin/Proposal roles can approve or lock sections or approve reusable library content.
- Pricing/cost section creation, editing, AI drafting, requirement traceability, revisions, and reusable pricing content remain behind existing financial permissions.
- Non-financial users can see that a pricing section exists in the response structure but receive no pricing content, revision count, mapped requirement details, or reusable pricing-library records.
- Editing previously approved content invalidates the approval unless an authorized approver explicitly approves the revised content in the same update.

## Production Live Web

- Adds one shared `core.live_web` service for ForgeAI, Capture Copilot, proposal research, direct Live Web research, and SBA fallback discovery.
- Explicit service states: `live`, `degraded`, `unavailable`, and `not_configured`.
- Normalized/deduplicated result schema with short-lived exact-query caching.
- Existing connector retry/backoff/circuit-breaker protections are reused for SearXNG.
- Cached exact-query results can be returned as `degraded`; ForgeGov never labels cached data as live.
- Direct Live Web API calls are authenticated and rate limited.
- Live Web failure is non-critical and does not take down government connectors, stored intelligence, or application readiness.

## Render private SearXNG

- `render.yaml` provisions `forgegov-searxng` as a private service (`pserv`).
- ForgeGov receives Render's private `host:port` through `SEARXNG_HOSTPORT`.
- `SEARXNG_HOSTPORT` takes precedence over any local/non-Render `SEARXNG_URL`, preventing an old Docker-only hostname from overriding production wiring.
- SearXNG JSON results are explicitly enabled.
- Local Compose and Render use the same pinned SearXNG image: `2026.8.17-374939b88`.
- Creator/Platform Owner receives a controlled Live Web probe in Platform Administration and system operations reports provider health.

## Live Web privacy boundary

Private AI prompts and document/workspace evidence are not used wholesale as external search queries.

- General ForgeAI chat searches the user's explicit question when Live Web is enabled.
- Proposal drafting uses public opportunity metadata (agency, solicitation number, title, section topic) as the separate web query.
- Capture Copilot uses public opportunity metadata and review mode as the separate web query.
- Opportunity-document analysis uses public opportunity metadata plus the explicit analysis task/question.

This prevents private proposal text, pipeline notes, modeled financial data, and indexed solicitation chunks from being forwarded as search-engine query text.

## Data model

Migration `core.0033_proposal_automation_live_web` creates:

- `ProposalVolume`
- `ProposalSection`
- `ProposalSectionRequirement`
- `ProposalSectionRevision`
- `ProposalLibraryEntry`

Live Web state is operational/cache state and does not require a database table.

## Validation

`VERIFY_V3.2.1.command` runs the 23-stage release gate. In addition to all historical tests, it includes the dedicated v3.2.1 proposal/live-web suite and a real uncached Django-to-SearXNG runtime probe. Do not push or tag until all 23 stages pass locally.
