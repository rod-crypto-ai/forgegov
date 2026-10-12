# ForgeGov v3.2.6 — ForgeAI Intelligence Platform

## Release purpose

Unify ForgeGov's existing AI chat, solicitation intelligence, capture copilot, proposal review, market intelligence, and authorized workspace evidence into one governed research platform without replacing deterministic workflows or allowing autonomous business-record changes.

## Included scope

- Server-backed ForgeAI research conversations instead of browser-local persistence.
- Research, opportunity, capture, proposal, and market workflow modes through one governed AI service.
- Unified, bounded grounding from official opportunities, stored awards, company profile, pipeline, pursuits, capture plans, opportunity workspaces, proposal plans and non-pricing proposal sections, tasks, contacts, and files.
- Role-filtered financial grounding; pricing content remains unavailable to unauthorized roles.
- Required separation of verified evidence, analysis and inferences, risks and unknowns, and recommended next actions.
- Source classification and provenance returned with every successful research response.
- Durable research-run provenance for provider, model, provider request IDs, token usage, source manifest, evidence summary, workflow, duration, and failure state.
- Database-enforced duplicate-running-request prevention with stale-run recovery.
- Organization-scoped platform status and recent-run reporting without exposing prompt text.
- Responsive ForgeAI research history, workflow selection, evidence counts, and coverage caveats.

## Explicit exclusions

- No autonomous bid/no-bid decisions, pursuit stage changes, proposal approvals, submissions, messages, or business-record mutations.
- No claim that source count or AI output proves completeness, correctness, health, readiness, approval, or legal compliance.
- No replacement of official-source connectors, deterministic capture gates, proposal review controls, or human approvals.
- No provider-side storage of OpenAI requests; `store` remains disabled.
- No new roadmap phase beyond v3.2.6.

## Migration

Migration `0040_v326_forgeai_intelligence_platform` adds `ForgeAIResearchRun`, its partial duplicate-run constraint, and organization/workflow indexes. It does not delete, merge, or rewrite existing user, conversation, opportunity, capture, proposal, or connector records.

## Security

- Every research request requires an active organization membership.
- Research runs, conversations, platform status, and private grounding remain organization scoped.
- Financial context is supplied only to Owner, Administrator, and Pricing roles.
- Private prompts are not exposed by the platform-status endpoint.
- Prompt-injection instructions embedded in records and web snippets remain untrusted and are explicitly ignored.
- Existing provider credentials remain server-side and are never returned to the frontend.
- ForgeAI provides decision support only; governed user actions remain explicit and attributable.

## Release gate

Full Django regression, v3.2.6 targeted tests, migration checks, lint, type-check, production build, Chromium/Firefox/WebKit responsive QA, dependency/security scans, non-root runtime checks, backup/restore, and production health/readiness must pass before release.
