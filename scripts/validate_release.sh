#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXPECTED_VERSION="3.1.3"

echo "[1/20] Source + release identity"
python3 -m compileall -q backend
python3 - <<'PY2'
import json, pathlib
root=pathlib.Path('.')
assert (root/'VERSION').read_text().strip() == '3.1.3'
package=json.loads((root/'frontend/package.json').read_text())
assert package['version'] == '3.1.3'
assert package['dependencies']['next'] == '16.3.1'
assert 'VERSION = "3.1.3"' in (root/'backend/core/version.py').read_text()
lock=json.loads((root/'frontend/package-lock.json').read_text())
assert lock['packages']['']['dependencies']['next'] == '16.3.1', 'secure Next.js lockfile baseline is missing'
assert lock['packages']['node_modules/next']['version'] == '16.3.1', 'installed Next.js lock entry is not the validated secure baseline'
print('Release identity: 3.1.3')
PY2

echo "[2/20] Private beta + capture-positioning source audit"
python3 scripts/private_beta_launch_audit.py

echo "[3/20] Docker Compose validation"
docker compose config --quiet

echo "[4/20] Build services"
docker compose build

echo "[5/20] Start services"
docker compose up -d

echo "[6/20] Django + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run

echo "[7/20] Backend regression"
docker compose exec backend python manage.py test core.tests platform_admin.tests platform_admin.test_v306_security --verbosity 1

echo "[8/20] v3.0.7 reliability tests"
docker compose exec backend python manage.py test core.test_v307_reliability --verbosity 2

echo "[9/20] v3.0.8 data integrity + connector resilience tests"
docker compose exec backend python manage.py test core.test_v308_integrity platform_admin.test_v308_integrity --verbosity 2

echo "[10/20] v3.0.9 governance + cross-tenant tests"
docker compose exec backend python manage.py test core.test_v309_governance platform_admin.test_v309_governance --verbosity 2

echo "[11/20] v3.1.0 private beta launch tests"
docker compose exec backend python manage.py test core.test_v310_launch_gate --verbosity 2

echo "[12/20] v3.1.1 beta stabilization + creator-control tests"
docker compose exec backend python manage.py test core.test_v311_beta_stabilization --verbosity 2

echo "[13/20] v3.1.2 alerts + notifications + daily intelligence tests"
docker compose exec backend python manage.py test core.test_v312_notifications platform_admin.test_v312_notifications --verbosity 2

echo "[14/20] v3.1.3 capture intelligence + competitive positioning tests"
docker compose exec backend python manage.py test core.test_v313_capture_positioning --verbosity 2

echo "[15/20] Frontend checks"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[16/20] Production-style Django security check"
docker compose run --rm \
  -e RUN_MIGRATIONS=false \
  -e COLLECTSTATIC=false \
  -e DJANGO_DEBUG=false \
  -e DJANGO_SECRET_KEY='ForgeGov-V313-Temporary-Deploy-Check-4a7d29eeb8a2409486b985be' \
  -e DJANGO_ALLOWED_HOSTS='forge-gov.com' \
  -e FRONTEND_URL='https://forge-gov.com' \
  -e CORS_ALLOWED_ORIGINS='https://forge-gov.com' \
  -e CSRF_TRUSTED_ORIGINS='https://forge-gov.com' \
  -e PUBLIC_REGISTRATION_ENABLED=true \
  -e REGISTRATION_MODE=public \
  -e SECURE_SSL_REDIRECT=true \
  -e SECURE_HSTS_SECONDS=31536000 \
  backend python manage.py check --deploy --fail-level WARNING

echo "[17/20] Dependency + tracked-secret security gate"
./scripts/security_release_scan.sh
docker run --rm \
  -v "$ROOT/backend/requirements.txt:/tmp/requirements.txt:ro" \
  python:3.13-slim \
  sh -lc 'python -m pip install --quiet pip-audit && pip-audit -r /tmp/requirements.txt'
docker compose run --rm frontend npm audit --omit=dev --audit-level=high

echo "[18/20] Runtime non-root checks"
for service in backend worker beat; do
  uid="$(docker compose exec -T "$service" id -u)"
  test "$uid" != "0" || { echo "$service is running as root"; exit 1; }
  echo "$service uid=$uid"
done

echo "[19/20] Backup + isolated restore verification"
BACKUP_PATH="backups/v313-release-verification.dump"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"
./scripts/backup_database.sh "$BACKUP_PATH"
./scripts/verify_backup_restore.sh "$BACKUP_PATH"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"

echo "[20/20] Health + readiness + container status"
EXPECTED_VERSION="$EXPECTED_VERSION" ./scripts/release_smoke.sh
docker compose ps

echo "ForgeGov v3.1.3 validation completed successfully."
