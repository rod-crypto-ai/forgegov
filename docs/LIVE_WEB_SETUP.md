# ForgeGov live web research

ForgeGov v2.0.3 includes a private local SearXNG service for live web research. The service is bound to `127.0.0.1:8080` and exposes JSON search to the ForgeGov backend.

## Local Docker setup

Run:

```bash
./scripts/enable_live_web.sh
```

The script safely updates `.env`, starts SearXNG, recreates the backend so it receives the new environment, and verifies the JSON search endpoint.

Expected settings:

```env
SEARXNG_URL=http://searxng:8080
SEARXNG_SECRET=<random secret>
AI_WEB_SEARCH_ENABLED=true
```

Then verify the complete release:

```bash
./scripts/validate_release.sh
```

## Hosted deployment

For Render or another hosted environment, deploy SearXNG separately or use a trusted private SearXNG endpoint. Set the backend environment variables:

```env
SEARXNG_URL=https://your-private-searxng.example
AI_WEB_SEARCH_ENABLED=true
```

The SearXNG instance must allow the JSON response format. ForgeGov reports `live`, `reconnecting`, `invalid_response`, or `disabled` instead of claiming live access when the search service cannot be reached.

## Security notes

- Keep the SearXNG instance private or access-controlled.
- Do not expose the local port beyond `127.0.0.1` unless you have added authentication and network restrictions.
- Rotate `SEARXNG_SECRET` for non-development use.
