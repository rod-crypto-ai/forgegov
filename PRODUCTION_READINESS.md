# ForgeGov v2.0 Production Readiness

## Release status
This package is the production-cleanup candidate for ForgeGov v2.0. It removes unfinished navigation surfaces, updates frontend versioning, disables public registration by default on Render, and separates local development from production Docker execution.

## Required validation
Run from the repository root:

```bash
docker compose down --remove-orphans
docker compose build --no-cache
docker compose up -d
docker compose exec backend python manage.py check
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test core
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

## Production-mode Docker smoke test

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
- `OPENAI_API_KEY`
- `NEXT_PUBLIC_API_BASE_URL`
- `PUBLIC_REGISTRATION_ENABLED=false` unless open signup is intentional

## Known limitation
Some official government sources prohibit browser embedding. ForgeGov must show a labeled official-source fallback for those records rather than claiming full in-app preview support.
