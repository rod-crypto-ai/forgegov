# ForgeGov v2.0.1 — Professional UX & Intelligence Release

## Product fixes
- Hardened SBA SUBNet with retries, 12-hour last-good caching, resilient parsing, source-health status, and non-blocking SAM subaward loading.
- Added first-class intelligence workspaces for agencies, forecasts, awards, and contract vehicles; company and opportunity workspaces remain directly linked.
- Fixed action-button overflow and wrapping across pipeline, teaming, compliance, and responsive layouts.
- Redesigned opportunity Compliance, Capture Notes, and Timeline views with guided headers, progress, structured cards, responsive controls, and clearer save actions.
- Redesigned contextual opportunity AI into structured findings cards with headings, bullets, source-aware language, and improved prompts.
- Redesigned ForgeGov AI with structured answers, source cards, provider status, and free-form GovCon research.

## Open-source AI and live web
- Added `AI_PROVIDER=openai|ollama`.
- Added self-hosted Ollama support through `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
- Added optional self-hosted SearXNG live web research through `SEARXNG_URL`.
- OpenAI remains supported as a hosted provider.
- AI answers continue to ground workspace facts and expose source labels.

## Required validation
Run `./scripts/validate_release.sh` after replacing the local project. Do not deploy unless every stage passes.
