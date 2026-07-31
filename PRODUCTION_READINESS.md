# ForgeGov v2.0.3 production readiness

## Release gate

Run from the repository root:

```bash
docker compose down --remove-orphans
docker compose build --no-cache
docker compose up -d
./scripts/enable_live_web.sh
./scripts/validate_release.sh
```

The release is approved only when all eight validation stages pass and the final line is:

```text
ForgeGov v2.0.3 validation completed successfully.
```

## Production-mode frontend smoke test

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml down --remove-orphans
docker compose -f docker-compose.yml -f docker-compose.production.yml build --no-cache frontend
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

## Required environment review

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `FRONTEND_URL`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `SAM_GOV_API_KEY`
- `NEXT_PUBLIC_API_BASE_URL`
- `AI_PROVIDER`
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`, or `OPENAI_API_KEY`
- `SEARXNG_URL`
- `SEARXNG_SECRET`
- `AI_WEB_SEARCH_ENABLED=true`
- `PUBLIC_REGISTRATION_ENABLED=false` unless open signup is intentional

## Staging smoke path

1. Sign in.
2. Search federal contract opportunities and open an internal detail workspace.
3. Search federal grants and open a complete grant workspace.
4. Add one contract and one grant to the pipeline.
5. Open Subcontracting and verify a live, indexed, cached, or reconnecting SBA status without a fatal page error.
6. Open an agency, company, award, vehicle, and forecast through an internal ForgeGov link.
7. Ask ForgeGov AI a current-market question and confirm source labels and live-web status.
8. Evaluate saved searches and open a resulting contract or grant alert.

## External-source limitation

Some official government sources prohibit browser embedding or temporarily block automated server traffic. ForgeGov labels official-source fallbacks and degraded states instead of claiming that every record can always be rendered internally.
