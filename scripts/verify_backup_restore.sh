#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUP="${1:-}"
if [ -z "$BACKUP" ] || [ ! -f "$BACKUP" ]; then
  echo "Usage: $0 /path/to/forgegov-backup.dump" >&2
  exit 64
fi

SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-forgegov}"
TARGET="forgegov_restore_verify_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  docker compose exec -T "$SERVICE" dropdb -U "$DB_USER" --if-exists "$TARGET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'Creating isolated restore-verification database: %s\n' "$TARGET"
docker compose exec -T "$SERVICE" createdb -U "$DB_USER" "$TARGET"
docker compose exec -T "$SERVICE" pg_restore -U "$DB_USER" -d "$TARGET" --no-owner --no-acl < "$BACKUP"
MIGRATIONS="$(docker compose exec -T "$SERVICE" psql -U "$DB_USER" -d "$TARGET" -Atc 'SELECT COUNT(*) FROM django_migrations;' | tr -d '\r')"
case "$MIGRATIONS" in
  ''|*[!0-9]*) echo "FAIL: restored database did not return a migration count." >&2; exit 1 ;;
esac
printf 'Restore verification passed. django_migrations rows: %s\n' "$MIGRATIONS"
