#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXPECTED_VERSION="3.0.9"

echo "[1/14] Source + release identity"
python3 -m compileall -q backend
python3 - <<'PY'
import json, pathlib
root=pathlib.Path('.')
assert (root/'VERSION').read_text().strip() == '3.0.9'
assert json.loads((root/'frontend/package.json').read_text())['version'] == '3.0.9'
assert 'VERSION = "3.0.9"' in (root/'backend/core/version.py').read_text()
print('Release identity: 3.0.9')
PY

echo "[2/14] Docker Compose validation"
docker compose config --quiet

echo "[3/14] Build services"
docker compose build

echo "[4/14] Start services"
docker compose up -d

echo "[5/14] Django + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run

echo "[6/14] Backend regression"
docker compose exec backend python manage.py test core.tests platform_admin.tests platform_admin.test_v306_security --verbosity 1

echo "[7/14] v3.0.7 reliability tests"
docker compose exec backend python manage.py test core.test_v307_reliability --verbosity 2

echo "[8/14] v3.0.8 data integrity + connector resilience tests"
docker compose exec backend python manage.py test core.test_v308_integrity platform_admin.test_v308_integrity --verbosity 2

echo "[9/14] v3.0.9 governance + cross-tenant tests"
docker compose exec backend python manage.py test core.test_v309_governance platform_admin.test_v309_governance --verbosity 2

echo "[10/14] Frontend checks"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[11/14] Runtime non-root checks"
for service in backend worker beat; do
  uid="$(docker compose exec -T "$service" id -u)"
  test "$uid" != "0" || { echo "$service is running as root"; exit 1; }
  echo "$service uid=$uid"
done

echo "[12/14] Backup + isolated restore verification"
BACKUP_PATH="backups/v309-release-verification.dump"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"
./scripts/backup_database.sh "$BACKUP_PATH"
./scripts/verify_backup_restore.sh "$BACKUP_PATH"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"

echo "[13/14] Health + readiness smoke"
EXPECTED_VERSION="$EXPECTED_VERSION" ./scripts/release_smoke.sh

echo "[14/14] Container status"
docker compose ps

echo "ForgeGov v3.0.9 validation completed successfully."
