#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXPECTED_VERSION="3.1.2"

echo "[1/19] Source + release identity"
python3 -m compileall -q backend
python3 - <<'PY2'
import json, pathlib
root=pathlib.Path('.')
assert (root/'VERSION').read_text().strip() == '3.1.2'
package=json.loads((root/'frontend/package.json').read_text())
assert package['version'] == '3.1.2'
assert package['dependencies']['next'] == '16.3.1'
assert 'VERSION = "3.1.2"' in (root/'backend/core/version.py').read_text()
lock=json.loads((root/'frontend/package-lock.json').read_text())
assert lock['packages']['']['dependencies']['next'] == '16.3.1', 'secure Next.js lockfile baseline is missing'
assert lock['packages']['node_modules/next']['version'] == '16.3.1', 'installed Next.js lock entry is not the validated secure baseline'
print('Release identity: 3.1.2')
PY2

echo "[2/19] Private beta + notification source audit"
python3 scripts/private_beta_launch_audit.py

echo "[3/19] Docker Compose validation"
docker compose config --quiet

echo "[4/19] Build services"
docker compose build

echo "[5/19] Start services"
docker compose up -d

echo "[6/19] Django + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run

echo "[7/19] Backend regression"
docker compose exec backend python manage.py test core.tests platform_admin.tests platform_admin.test_v306_security --verbosity 1

echo "[8/19] v3.0.7 reliability tests"
docker compose exec backend python manage.py test core.test_v307_reliability --verbosity 2

echo "[9/19] v3.0.8 data integrity + connector resilience tests"
docker compose exec backend python manage.py test core.test_v308_integrity platform_admin.test_v308_integrity --verbosity 2

echo "[10/19] v3.0.9 governance + cross-tenant tests"
docker compose exec backend python manage.py test core.test_v309_governance platform_admin.test_v309_governance --verbosity 2

echo "[11/19] v3.1.0 private beta launch tests"
docker compose exec backend python manage.py test core.test_v310_launch_gate --verbosity 2

echo "[12/19] v3.1.1 beta stabilization + creator-control tests"
docker compose exec backend python manage.py test core.test_v311_beta_stabilization --verbosity 2

echo "[13/19] v3.1.2 alerts + notifications + daily intelligence tests"
docker compose exec backend python manage.py test core.test_v312_notifications platform_admin.test_v312_notifications --verbosity 2

echo "[14/19] Frontend checks"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[15/19] Production-style Django security check"
docker compose run --rm \
  -e RUN_MIGRATIONS=false \
  -e COLLECTSTATIC=false \
  -e DJANGO_DEBUG=false \
  -e DJANGO_SECRET_KEY='ForgeGov-V312-Temporary-Deploy-Check-19f42c8631b94a7081be7ef6' \
  -e DJANGO_ALLOWED_HOSTS='forge-gov.com' \
  -e FRONTEND_URL='https://forge-gov.com' \
  -e CORS_ALLOWED_ORIGINS='https://forge-gov.com' \
  -e CSRF_TRUSTED_ORIGINS='https://forge-gov.com' \
  -e PUBLIC_REGISTRATION_ENABLED=true \
  -e REGISTRATION_MODE=public \
  -e SECURE_SSL_REDIRECT=true \
  -e SECURE_HSTS_SECONDS=31536000 \
  backend python manage.py check --deploy --fail-level WARNING

echo "[16/19] Dependency + tracked-secret security gate"
./scripts/security_release_scan.sh
docker run --rm \
  -v "$ROOT/backend/requirements.txt:/tmp/requirements.txt:ro" \
  python:3.13-slim \
  sh -lc 'python -m pip install --quiet pip-audit && pip-audit -r /tmp/requirements.txt'
docker compose run --rm frontend npm audit --omit=dev --audit-level=high

echo "[17/19] Runtime non-root checks"
for service in backend worker beat; do
  uid="$(docker compose exec -T "$service" id -u)"
  test "$uid" != "0" || { echo "$service is running as root"; exit 1; }
  echo "$service uid=$uid"
done

echo "[18/19] Backup + isolated restore verification"
BACKUP_PATH="backups/v312-release-verification.dump"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"
./scripts/backup_database.sh "$BACKUP_PATH"
./scripts/verify_backup_restore.sh "$BACKUP_PATH"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"

echo "[19/19] Health + readiness + container status"
EXPECTED_VERSION="$EXPECTED_VERSION" ./scripts/release_smoke.sh
docker compose ps

echo "ForgeGov v3.1.2 validation completed successfully."
