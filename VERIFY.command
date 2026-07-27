#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[1/10] Checking source and script syntax"
python3 -m compileall -q backend scripts
bash -n INSTALL.command VERIFY.command backend/entrypoint.sh
python3 - <<'PY'
import json
from pathlib import Path
for path in (Path("frontend/package.json"), Path("frontend/package-lock.json"), Path("frontend/tsconfig.json")):
    json.loads(path.read_text())
print("Source metadata is valid JSON.")
PY

echo "[2/10] Checking release files and known regressions"
test -f frontend/app/sign-in/page.tsx
test -f frontend/app/register/page.tsx
test -f backend/core/ai.py
test -f backend/core/migrations/0005_fix_pending_invitation_constraint.py
! grep -Rqs 'packages.applied-caas-gateway1.internal.api.openai.org' frontend/package-lock.json
grep -q 'basename="organization"' backend/core/urls.py
grep -q 'path("ai/chat/", ai_chat)' backend/core/urls.py
grep -q 'credentials: "include"' frontend/lib/api.ts
grep -q 'Loading the most recent live opportunities' frontend/components/opportunity-explorer.tsx
grep -q 'Suspense' frontend/app/sign-in/page.tsx
grep -q 'Suspense' frontend/app/register/page.tsx

echo "[3/10] Validating Docker Compose"
docker compose config >/dev/null

echo "[4/10] Building services"
docker compose build backend frontend

echo "[5/10] Starting services with current .env values"
docker compose up -d --force-recreate
sleep 15

echo "[6/10] Running Django checks, migration checks, and tests"
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T backend python manage.py test core

echo "[7/10] Verifying live SAM.gov opportunity access"
docker compose exec -T backend python manage.py shell <<'PY_SAM'
from django.conf import settings
from core.integrations import search_sam_opportunities

assert settings.SAM_GOV_API_KEY, "SAM_GOV_API_KEY is missing from .env"
result = search_sam_opportunities(limit=1, persist=False)
print("SAM.gov live search passed: {} records available".format(result["total_records"]))
PY_SAM

echo "[8/10] Verifying OpenAI server-side configuration and API access"
docker compose exec -T backend python manage.py shell <<'PY'
from django.conf import settings
import requests

assert settings.OPENAI_API_KEY, "OPENAI_API_KEY is missing from .env"
response = requests.post(
    f"{settings.OPENAI_API_BASE_URL.rstrip('/')}/responses",
    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
    json={"model": settings.OPENAI_MODEL, "input": "Reply with exactly: ForgeGov OpenAI verified", "max_output_tokens": 80, "store": False},
    timeout=settings.OPENAI_TIMEOUT_SECONDS,
)
try:
    payload = response.json()
except ValueError:
    payload = {"raw": response.text[:500]}
assert response.ok, f"OpenAI verification failed ({response.status_code}): {payload}"
print(f"OpenAI verification passed with model {payload.get('model', settings.OPENAI_MODEL)}")
PY

echo "[9/10] Running frontend lint, type checking, and production build"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npx tsc --noEmit
docker build --target runner -t forgegov-frontend-production ./frontend

echo "[10/10] Checking local health endpoints"
curl --fail --silent http://localhost:8000/api/health/ >/dev/null
curl --fail --silent http://localhost:3000 >/dev/null

echo "ForgeGov v1.0.2 verification passed."
