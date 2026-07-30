#!/usr/bin/env bash
set -euo pipefail

echo "[1/7] Django system check"
docker compose exec backend python manage.py check

echo "[2/7] Database migrations"
docker compose exec backend python manage.py migrate --check

echo "[3/7] Backend tests"
docker compose exec backend python manage.py test core

echo "[4/7] Frontend typecheck"
docker compose exec frontend npm run typecheck

echo "[5/7] Frontend lint"
docker compose exec frontend npm run lint

echo "[6/7] Frontend production build"
docker compose exec frontend npm run build

echo "[7/7] Container status"
docker compose ps

echo "ForgeGov v2.0 validation completed successfully."
