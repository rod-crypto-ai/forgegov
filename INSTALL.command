#!/bin/bash
set -euo pipefail

PROJECT="$HOME/Documents/GitHub/forgegov"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP="$HOME/Documents/GitHub/forgegov-backup-$(date +%Y%m%d-%H%M%S)"

echo "ForgeGov v1.2.0 federal data expansion installer"
if [ ! -f "$PROJECT/docker-compose.yml" ]; then
  echo "ERROR: ForgeGov was not found at $PROJECT"
  exit 1
fi

echo "Creating backup: $BACKUP"
cp -R "$PROJECT" "$BACKUP"

cd "$PROJECT"
docker compose down --remove-orphans || true

echo "Installing v1.2.0 while preserving .git and .env..."
rsync -a \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='node_modules' \
  --exclude='.next' \
  "$PACKAGE_DIR/" "$PROJECT/"

python3 -m compileall -q backend
grep -q 'path("ai/chat/", ai_chat)' backend/core/urls.py
grep -q 'OPENAI_API_KEY' backend/forgegov/settings.py
grep -q 'Loading the most recent live opportunities' frontend/components/opportunity-explorer.tsx

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your SAM.gov and OpenAI keys before using those integrations."
else
  grep -Eq '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=' .env || printf '\nOPENAI_API_KEY=\n' >> .env
  grep -Eq '^[[:space:]]*OPENAI_API_BASE_URL[[:space:]]*=' .env || printf 'OPENAI_API_BASE_URL=https://api.openai.com/v1\n' >> .env
  grep -Eq '^[[:space:]]*OPENAI_MODEL[[:space:]]*=' .env || printf 'OPENAI_MODEL=gpt-5-mini\n' >> .env
  grep -Eq '^[[:space:]]*OPENAI_TIMEOUT_SECONDS[[:space:]]*=' .env || printf 'OPENAI_TIMEOUT_SECONDS=90\n' >> .env
  grep -Eq '^[[:space:]]*OPENAI_MAX_OUTPUT_TOKENS[[:space:]]*=' .env || printf 'OPENAI_MAX_OUTPUT_TOKENS=1800\n' >> .env
  grep -Eq '^[[:space:]]*OPENAI_CHAT_RATE[[:space:]]*=' .env || printf 'OPENAI_CHAT_RATE=60/hour\n' >> .env
  grep -Eq '^[[:space:]]*SAM_SUBAWARDS_BASE_URL[[:space:]]*=' .env || printf 'SAM_SUBAWARDS_BASE_URL=https://api.sam.gov/prod/contract/v1/subcontracts/search\n' >> .env
  grep -Eq '^[[:space:]]*SBA_SUBNET_URL[[:space:]]*=' .env || printf 'SBA_SUBNET_URL=https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities\n' >> .env
  grep -Eq '^[[:space:]]*ALERTS_ENABLED[[:space:]]*=' .env || printf 'ALERTS_ENABLED=true\n' >> .env
fi

echo "Rebuilding and recreating ForgeGov containers so updated environment variables are loaded..."
chmod +x INSTALL.command VERIFY.command backend/entrypoint.sh
docker compose build --no-cache backend frontend
docker compose up -d --force-recreate
sleep 15
docker compose ps

echo
echo "ForgeGov v1.2.0 installed. Open http://localhost:3000"
echo "Run ./VERIFY.command for the full verification suite, including an OpenAI API probe when a key is configured."
