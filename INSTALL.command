#!/bin/bash
set -e
PROJECT="$HOME/Documents/GitHub/forgegov"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "ForgeGov v0.8 functional-workflows installer"
if [ ! -f "$PROJECT/docker-compose.yml" ]; then echo "ERROR: ForgeGov was not found at $PROJECT"; exit 1; fi
BACKUP="$HOME/Documents/GitHub/forgegov-backup-$(date +%Y%m%d-%H%M%S)"
echo "Creating backup: $BACKUP"
cp -R "$PROJECT" "$BACKUP"
[ -f "$PROJECT/.env" ] && cp "$PROJECT/.env" "$HOME/forgegov-env-backup"
cd "$PROJECT"
docker compose down --remove-orphans || true
echo "Installing v0.8 source..."
rsync -a --delete --exclude=".git" --exclude=".env" --exclude="node_modules" --exclude=".next" "$PACKAGE_DIR/" "$PROJECT/"
[ -f "$HOME/forgegov-env-backup" ] && cp "$HOME/forgegov-env-backup" "$PROJECT/.env"
grep -q "Add to pipeline" "$PROJECT/frontend/components/opportunity-explorer.tsx" || { echo "ERROR: v0.8 frontend files were not installed"; exit 1; }
grep -q "opportunity-to-pipeline" "$PROJECT/backend/core/urls.py" || { echo "ERROR: v0.8 backend files were not installed"; exit 1; }
cd "$PROJECT"
echo "Building backend and frontend..."
docker compose build backend frontend
echo "Starting ForgeGov and applying migrations..."
docker compose up -d
docker compose ps
echo
echo "ForgeGov v0.8 installed. Open http://localhost:3000"
