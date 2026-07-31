# ForgeGov v2.0.3

ForgeGov is a government-contracting intelligence and capture-management platform built with Django, Django REST Framework, PostgreSQL, Redis, Celery, Next.js, TypeScript, and Docker.

## Core capabilities

- Live SAM.gov federal contract opportunity search and internal opportunity workspaces.
- Live Grants.gov search with complete grant detail workspaces, documents, funding intelligence, compliance, notes, timeline, pipeline actions, and contextual AI.
- Resilient SBA SUBNet discovery with live, indexed, cached, and stored-history fallbacks.
- SAM.gov subaward intelligence, USAspending awards and contract vehicles, federal forecasts, agency profiles, company profiles, teaming, alerts, pipeline, and pursuits.
- Interactive links for opportunities, grants, companies, agencies, awards, vehicles, and forecasts.
- ForgeGov AI grounded in organization-scoped workspace records, government data, and optional live web research.
- OpenAI or self-hosted Ollama model provider.
- Private local SearXNG service for live web search.

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
SEARXNG_SECRET=<long random secret>
AI_WEB_SEARCH_ENABLED=true
```

OpenAI remains available as an optional hosted provider by setting `AI_PROVIDER=openai` and a server-side `OPENAI_API_KEY`. Never expose API keys through `NEXT_PUBLIC_*` variables.

## Validate before release

```bash
./scripts/validate_release.sh
```

The validator checks Django, migrations, all backend tests, TypeScript, ESLint, the production Next.js build, SearXNG JSON search, and running containers. Do not tag or deploy the release unless it ends with:

```text
ForgeGov v2.0.3 validation completed successfully.
```

## Production notes

- Public registration should remain disabled unless self-service signup is intentional.
- Configure production CORS, CSRF, allowed hosts, secure cookies, HSTS, and frontend/API URLs.
- Hosted deployments must supply a private `SEARXNG_URL`; the local Docker hostname is not valid outside Docker Compose.
- External official-source links remain available when an upstream site blocks safe embedding.
