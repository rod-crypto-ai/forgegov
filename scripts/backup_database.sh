#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-forgegov}"
DB_NAME="${DB_NAME:-forgegov}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="${1:-$BACKUP_DIR/forgegov-$STAMP.dump}"

printf 'Creating PostgreSQL backup: %s\n' "$OUTPUT"
docker compose exec -T "$SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner --no-acl > "$OUTPUT"
test -s "$OUTPUT"
docker compose exec -T "$SERVICE" pg_restore --list < "$OUTPUT" >/dev/null

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$OUTPUT" > "$OUTPUT.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$OUTPUT" > "$OUTPUT.sha256"
fi
printf 'Backup created and catalog verified: %s\n' "$OUTPUT"
