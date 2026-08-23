#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXPECTED_VERSION="3.2.1.2"

echo "[1/24] Source + release identity"
python3 -m compileall -q backend
python3 - <<'PY2'
import json, pathlib
root=pathlib.Path('.')
assert (root/'VERSION').read_text().strip() == '3.2.1.2'
package=json.loads((root/'frontend/package.json').read_text())
assert package['version'] == '3.2.1-2'
assert package['dependencies']['next'] == '16.3.1'
assert 'VERSION = "3.2.1.2"' in (root/'backend/core/version.py').read_text()
lock=json.loads((root/'frontend/package-lock.json').read_text())
assert lock['packages']['']['dependencies']['next'] == '16.3.1', 'secure Next.js lockfile baseline is missing'
assert lock['packages']['node_modules/next']['version'] == '16.3.1', 'installed Next.js lock entry is not the validated secure baseline'
print('Release identity: 3.2.1.2 (frontend npm 3.2.1-2)')
PY2

echo "[2/24] Release source + production architecture audit"
python3 scripts/private_beta_launch_audit.py

echo "[3/24] Docker Compose validation"
docker compose config --quiet

echo "[4/24] Build services"
docker compose build

echo "[5/24] Start services"
docker compose up -d

echo "[6/24] Django + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run

echo "[7/24] Backend regression"
docker compose exec backend python manage.py test core.tests platform_admin.tests platform_admin.test_v306_security --verbosity 1

echo "[8/24] v3.0.7 reliability tests"
docker compose exec backend python manage.py test core.test_v307_reliability --verbosity 2

echo "[9/24] v3.0.8 data integrity + connector resilience tests"
docker compose exec backend python manage.py test core.test_v308_integrity platform_admin.test_v308_integrity --verbosity 2

echo "[10/24] v3.0.9 governance + cross-tenant tests"
docker compose exec backend python manage.py test core.test_v309_governance platform_admin.test_v309_governance --verbosity 2

echo "[11/24] v3.1.0 private beta launch tests"
docker compose exec backend python manage.py test core.test_v310_launch_gate --verbosity 2

echo "[12/24] v3.1.1 beta stabilization + creator-control tests"
docker compose exec backend python manage.py test core.test_v311_beta_stabilization --verbosity 2

echo "[13/24] v3.1.2 alerts + notifications + daily intelligence tests"
docker compose exec backend python manage.py test core.test_v312_notifications platform_admin.test_v312_notifications --verbosity 2

echo "[14/24] v3.1.3 capture intelligence + competitive positioning tests"
docker compose exec backend python manage.py test core.test_v313_capture_positioning --verbosity 2

echo "[15/24] v3.2.0 Capture Copilot + Settings Center tests"
docker compose exec backend python manage.py test core.test_v320_capture_copilot_settings --verbosity 2

echo "[16/24] v3.2.1 proposal automation + live-web tests"
docker compose exec backend python manage.py test core.test_v321_proposal_live_web --verbosity 2

echo "[17/24] v3.2.1.2 Microsoft connection verification + integration regression tests"
docker compose exec backend python manage.py test core.test_v3211_integrations_ux --verbosity 2

echo "[18/24] Live Web runtime connectivity"
docker compose exec backend python manage.py shell -c 'from core.live_web import search; r=search("federal acquisition forecast", limit=1, timeout=15, allow_cached=False); print(r); assert r.get("status") == "live" and r.get("reachable") is True, r'

echo "[19/24] Frontend checks"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[20/24] Production-style Django security check"
docker compose run --rm \
  -e RUN_MIGRATIONS=false \
  -e COLLECTSTATIC=false \
  -e DJANGO_DEBUG=false \
  -e DJANGO_SECRET_KEY='ForgeGov-V32112-Temporary-Deploy-Check-864c5f20cb0a42fa918bf9fd' \
  -e DJANGO_ALLOWED_HOSTS='forge-gov.com' \
  -e FRONTEND_URL='https://forge-gov.com' \
  -e CORS_ALLOWED_ORIGINS='https://forge-gov.com' \
  -e CSRF_TRUSTED_ORIGINS='https://forge-gov.com' \
  -e PUBLIC_REGISTRATION_ENABLED=true \
  -e REGISTRATION_MODE=public \
  -e SECURE_SSL_REDIRECT=true \
  -e SECURE_HSTS_SECONDS=31536000 \
  backend python manage.py check --deploy --fail-level WARNING

echo "[21/24] Dependency + tracked-secret security gate"
./scripts/security_release_scan.sh
docker run --rm \
  -v "$ROOT/backend/requirements.txt:/tmp/requirements.txt:ro" \
  python:3.13-slim \
  sh -lc 'python -m pip install --quiet pip-audit && pip-audit -r /tmp/requirements.txt'
docker compose run --rm frontend npm audit --omit=dev --audit-level=high

echo "[22/24] Runtime non-root checks"
for service in backend worker beat; do
  uid="$(docker compose exec -T "$service" id -u)"
  test "$uid" != "0" || { echo "$service is running as root"; exit 1; }
  echo "$service uid=$uid"
done

echo "[23/24] Backup + isolated restore verification"
BACKUP_PATH="backups/v3211-release-verification.dump"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"
./scripts/backup_database.sh "$BACKUP_PATH"
./scripts/verify_backup_restore.sh "$BACKUP_PATH"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"

echo "[24/24] Health + readiness + container status"
EXPECTED_VERSION="$EXPECTED_VERSION" ./scripts/release_smoke.sh
docker compose ps

echo "ForgeGov v3.2.1.2 validation completed successfully."
