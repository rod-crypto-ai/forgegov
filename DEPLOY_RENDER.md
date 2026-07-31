# Deploy ForgeGov v2.0.3 on Render

ForgeGov's `render.yaml` provisions PostgreSQL, Redis, the Django API, Celery worker, Celery scheduler, and Next.js frontend. SearXNG is intentionally not auto-provisioned because it should be deployed as a private service with controlled access.

## Required API environment values

Set these secrets and URLs on `forgegov-api`:

```env
DJANGO_ALLOWED_HOSTS=<api host>
FRONTEND_URL=https://<frontend host>
CORS_ALLOWED_ORIGINS=https://<frontend host>
CSRF_TRUSTED_ORIGINS=https://<frontend host>
API_PUBLIC_URL=https://<api host>
SAM_GOV_API_KEY=<secret>
AI_PROVIDER=ollama
OLLAMA_BASE_URL=https://<private ollama endpoint>
OLLAMA_MODEL=<installed model>
SEARXNG_URL=https://<private searxng endpoint>
AI_WEB_SEARCH_ENABLED=true
```

OpenAI can be used instead by setting `AI_PROVIDER=openai` and `OPENAI_API_KEY`.

## Frontend environment

Set:

```env
NEXT_PUBLIC_API_BASE_URL=https://<api host>/api
```

## SearXNG

Deploy SearXNG privately and enable JSON search responses. Do not point production at `http://searxng:8080` unless SearXNG is in the same private network and that hostname resolves from the API service.

## Release procedure

1. Deploy a staging environment from the exact release tag.
2. Apply migrations through the API service startup.
3. Verify `/api/health/`.
4. Sign in and test contracts, grants, subcontracting, pipeline, alerts, and ForgeGov AI.
5. Confirm `/api/integrations/status/?probe=true` reports the intended AI provider and SearXNG state.
6. Promote the same commit only after `./scripts/validate_release.sh` has passed locally.
