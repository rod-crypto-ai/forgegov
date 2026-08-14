#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/10] Source and conflict checks"
python3 -m compileall -q backend
if grep -RniE '^(<<<<<<<|=======|>>>>>>>)' backend frontend --exclude-dir=node_modules --exclude-dir=.next; then
  echo "FAIL: merge conflict markers found"
  exit 1
fi

echo "[2/10] Release identity checks"
python3 - <<'PY'
import json, pathlib, re
root=pathlib.Path(".")
pkg=json.loads((root/"frontend/package.json").read_text())
assert pkg["version"]=="3.0.5", pkg["version"]
assert (root/"VERSION").read_text().strip()=="3.0.5"
views=(root/"backend/core/views.py").read_text()
assert '"version": "3.0.5"' in views or "'version': '3.0.5'" in views
print("Release identity: 3.0.5")
PY

echo "[3/10] Docker Compose validation"
docker compose config >/dev/null

echo "[4/10] Build services"
docker compose build

echo "[5/10] Start containers"
docker compose up -d
docker compose ps

echo "[6/10] Django system + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py migrate --noinput

echo "[7/10] Backend tests including platform administration"
docker compose exec backend python manage.py test core platform_admin --verbosity 2

echo "[8/10] Platform-admin route/security smoke checks"
docker compose exec backend python manage.py shell -c '
from django.urls import resolve
assert resolve("/api/platform-admin/dashboard/")
print("Platform admin routes resolve.")
'

echo "[9/10] Frontend lint + typecheck + production build"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[10/10] Runtime health/version verification"
python3 - <<'PY'
import json, urllib.request
url="http://localhost:8000/api/health/"
with urllib.request.urlopen(url, timeout=20) as r:
    data=json.load(r)
assert data.get("status")=="ok", data
assert data.get("product")=="ForgeGov", data
assert data.get("version")=="3.0.5", data
print(data)
PY

echo
echo "ForgeGov v3.0.5 verification passed."
