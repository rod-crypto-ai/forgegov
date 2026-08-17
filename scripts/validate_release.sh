#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXPECTED_VERSION="3.0.7"

echo "[1/12] Source + release identity"
python3 -m compileall -q backend
python3 - <<'PY'
import json, pathlib
root=pathlib.Path('.')
assert (root/'VERSION').read_text().strip() == '3.0.7'
assert json.loads((root/'frontend/package.json').read_text())['version'] == '3.0.7'
assert 'VERSION = "3.0.7"' in (root/'backend/core/version.py').read_text()
print('Release identity: 3.0.7')
PY

echo "[2/12] Docker Compose validation"
docker compose config --quiet

echo "[3/12] Build services"
docker compose build

echo "[4/12] Start services"
docker compose up -d

echo "[5/12] Django + migration checks"
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run

echo "[6/12] Backend regression"
docker compose exec backend python manage.py test core.tests platform_admin.tests platform_admin.test_v306_security --verbosity 1

echo "[7/12] v3.0.7 reliability tests"
docker compose exec backend python manage.py test core.test_v307_reliability --verbosity 2

echo "[8/12] Frontend checks"
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build

echo "[9/12] Runtime non-root checks"
for service in backend worker beat; do
  uid="$(docker compose exec -T "$service" id -u)"
  test "$uid" != "0" || { echo "$service is running as root"; exit 1; }
  echo "$service uid=$uid"
done

echo "[10/12] Backup + isolated restore verification"
BACKUP_PATH="backups/v307-release-verification.dump"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"
./scripts/backup_database.sh "$BACKUP_PATH"
./scripts/verify_backup_restore.sh "$BACKUP_PATH"
rm -f "$BACKUP_PATH" "$BACKUP_PATH.sha256"

echo "[11/12] Health + readiness smoke"
EXPECTED_VERSION="$EXPECTED_VERSION" ./scripts/release_smoke.sh

echo "[12/12] Container status"
docker compose ps

echo "ForgeGov v3.0.7 validation completed successfully."
