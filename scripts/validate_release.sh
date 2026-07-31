#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/8] Django system check"
docker compose exec backend python manage.py check

echo "[2/8] Database migrations"
docker compose exec backend python manage.py migrate --check

echo "[3/8] Backend tests"
docker compose exec backend python manage.py test core

echo "[4/8] Frontend typecheck"
docker compose exec frontend npm run typecheck

echo "[5/8] Frontend lint"
docker compose exec frontend npm run lint

echo "[6/8] Frontend production build"
docker compose exec frontend npm run build

echo "[7/8] Live web search probe"
docker compose exec -T backend python manage.py shell -c 'from django.core.cache import cache; from core.ai import live_web_status; cache.delete("forgegov:searxng:health:v1"); result=live_web_status(probe=True); assert result.get("configured"), result; assert result.get("reachable"), result; print("ForgeGov live web search passed:", result)'

echo "[8/8] Container status"
docker compose ps

echo "ForgeGov v2.0.3 validation completed successfully."
