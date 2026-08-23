# ForgeGov v3.2.1

ForgeGov is a government-contracting intelligence and capture-management platform built with Django, Django REST Framework, PostgreSQL, Redis, Celery, Next.js, TypeScript, and Docker.

## Core capabilities

- Live SAM.gov federal contract opportunity search and internal opportunity workspaces.
- Live Grants.gov search with complete grant detail workspaces, documents, funding intelligence, compliance, notes, timeline, pipeline actions, and contextual AI.
- Resilient SBA SUBNet discovery with live, indexed, cached, and stored-history fallbacks.
- SAM.gov subaward intelligence, USAspending awards and contract vehicles, federal forecasts, agency profiles, company profiles, teaming, alerts, pipeline, and pursuits.
- Interactive links for opportunities, grants, companies, agencies, awards, vehicles, and forecasts.
- Unified in-app/email intelligence notifications with saved-search matches, opportunity changes, deadlines, Project Room activity, and daily/weekly briefs.
- ForgeAI Capture Copilot with evidence-backed pursuit posture, competitor review, bid-decision challenge, proposal strategy, red-team review, and next-action planning.
- Persistent Settings Center with system/light/dark themes, density, reduced motion, sidebar preference, AI behavior controls, notifications, account/workspace links, and security links.
- ForgeGov AI grounded in role-authorized organization workspace records, government data, and optional live web research.
- OpenAI or self-hosted Ollama model provider.
- Production-grade private SearXNG live-web service with explicit health states, normalized results, retry/circuit protection, and cached fallback.
- Proposal production workspace with structured volumes/sections, requirement traceability, revisions, reusable approved content, evidence-grounded ForgeAI drafting, and package validation.

## Local installation

Copy `.env.example` to `.env` when starting a new installation and set at least the required database/security and government-data values. Existing upgrades should preserve the current `.env`.

```bash
cp .env.example .env

docker compose build --no-cache
docker compose up -d
```

Open:

- ForgeGov: `http://localhost:3000`
- API health: `http://localhost:8000/api/health/`
- Contracts: `http://localhost:3000/opportunities/federal-contracts`
- Grants: `http://localhost:3000/opportunities/federal-grants`
- Subcontracting: `http://localhost:3000/opportunities/subcontracting`
- ForgeGov AI: `http://localhost:3000/assistant`
- Settings Center: `http://localhost:3000/settings`

## Enable live web research

```bash
./scripts/enable_live_web.sh
```

This configures the backend to use the bundled private SearXNG service at `http://searxng:8080`, recreates the backend, and verifies JSON search.

See `docs/LIVE_WEB_SETUP.md` for hosted deployment guidance.

## Enable the open-source AI provider

Install Ollama and the desired model on the Mac, then run:

```bash
ollama pull qwen3:8b
./scripts/enable_open_source_ai.sh
```

See `docs/AI_OPEN_SOURCE_SETUP.md` for provider switching and model selection.

## Important environment values

```env
SAM_GOV_API_KEY=<SAM.gov API key>
DJANGO_SECRET_KEY=<long random secret>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api

AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:8b

SEARXNG_URL=http://searxng:8080
SEARXNG_HOSTPORT=
SEARXNG_SECRET=<long random secret>
AI_WEB_SEARCH_ENABLED=true
LIVE_WEB_CACHE_SECONDS=600
```

OpenAI remains available as an optional hosted provider by setting `AI_PROVIDER=openai` and a server-side `OPENAI_API_KEY`. Never expose API keys through `NEXT_PUBLIC_*` variables.

## Validate before release

```bash
./scripts/validate_release.sh
```

The 23-stage validator checks Django, migrations, all historical and v3.2.1 backend tests, an uncached backend-to-SearXNG runtime probe, TypeScript, ESLint, the production Next.js build, dependency/security gates, backup/restore, and running containers. Do not tag or deploy the release unless it ends with:

```text
ForgeGov v3.2.1 validation completed successfully.
```

## Production notes

- Registration mode is runtime-controlled by the Creator/Platform Owner; verify the intended public/private-beta/invite-only/closed mode before production changes.
- Configure production CORS, CSRF, allowed hosts, secure cookies, HSTS, and frontend/API URLs.
- Render deployments provision `forgegov-searxng` as a private service and inject its private `host:port` into the API. The Render private host takes precedence over any manual URL; `SEARXNG_URL` remains a local/non-Render override only.
- External official-source links remain available when an upstream site blocks safe embedding.
