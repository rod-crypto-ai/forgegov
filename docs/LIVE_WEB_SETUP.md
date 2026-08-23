# ForgeGov live web research

ForgeGov v3.2.1 includes a shared SearXNG live-web service for local and hosted research. The service is bound to `127.0.0.1:8080` and exposes JSON search to the ForgeGov backend.

## Local Docker setup

Run:

```bash
./scripts/enable_live_web.sh
```

The script safely updates `.env`, starts SearXNG, recreates the backend so it receives the new environment, and verifies the JSON search endpoint.

Expected local settings:

```env
SEARXNG_URL=http://searxng:8080
SEARXNG_HOSTPORT=
SEARXNG_SECRET=<random secret>
AI_WEB_SEARCH_ENABLED=true
LIVE_WEB_CACHE_SECONDS=600
```

ForgeGov pins the local and production SearXNG image to `2026.8.17-374939b88` for release reproducibility.

Then verify the complete release:

```bash
./scripts/validate_release.sh
```

## Hosted deployment

ForgeGov's Render Blueprint provisions `forgegov-searxng` as a `pserv` private service. The API receives the service's internal `host:port` through `SEARXNG_HOSTPORT`, and Django constructs the internal HTTP URL. `SEARXNG_HOSTPORT` deliberately takes precedence over `SEARXNG_URL`, preventing a stale Docker-only URL from breaking production after deployment. No public SearXNG URL is required.

For non-Render environments, set:

```env
SEARXNG_URL=https://your-private-searxng.example
AI_WEB_SEARCH_ENABLED=true
LIVE_WEB_CACHE_SECONDS=600
```

The SearXNG instance must allow JSON output. ForgeGov reports `live`, `degraded`, `unavailable`, or `not_configured`. A degraded result can use the latest cached result for that exact query while government connectors and stored ForgeGov records continue operating independently.

Use these authenticated API checks:

```text
GET /api/live-web/status/?probe=true
GET /api/live-web/search/?q=federal%20acquisition%20forecast
```

The Creator/Platform Owner can also run the connector test through `/api/platform-admin/live-web/test/`.

## Security notes

- Keep the SearXNG instance private or access-controlled.
- Do not expose the local port beyond `127.0.0.1` unless you have added authentication and network restrictions.
- Rotate `SEARXNG_SECRET` for non-development use.
- Private AI prompts are never forwarded wholesale as web-search queries. Proposal drafting, Capture Copilot, and opportunity-document analysis build a separate search query from public opportunity metadata such as agency, solicitation number, title, and the user's explicit research question.
- Live Web is a non-critical dependency: an outage must not mark SAM.gov, USAspending, stored ForgeGov intelligence, or the ForgeGov application itself unavailable.
