#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add required SAM.gov/OpenAI credentials before production use."
fi

python3 - <<'PY'
from pathlib import Path
import secrets
path=Path('.env')
lines=path.read_text().splitlines()
updates={
    'SEARXNG_URL':'http://searxng:8080',
    # Render-only private host wiring must not override the local Compose URL.
    'SEARXNG_HOSTPORT':'',
    'AI_WEB_SEARCH_ENABLED':'true',
    'LIVE_WEB_CACHE_SECONDS':'600',
}
values={}
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key,value=line.split('=',1); values[key]=value
if not values.get('SEARXNG_SECRET') or values.get('SEARXNG_SECRET')=='replace-with-a-long-random-value':
    updates['SEARXNG_SECRET']=secrets.token_hex(32)
for key,value in updates.items():
    found=False
    for index,line in enumerate(lines):
        if line.startswith(key+'='):
            lines[index]=f'{key}={value}'; found=True; break
    if not found: lines.append(f'{key}={value}')
path.write_text('\n'.join(lines)+'\n')
PY

echo "Starting private SearXNG and recreating the ForgeGov API with live-web settings..."
docker compose up -d searxng
docker compose up -d --force-recreate backend

echo "Waiting for SearXNG JSON search..."
for attempt in $(seq 1 30); do
  if curl -fsS --get 'http://127.0.0.1:8080/search' --data-urlencode 'q=federal contracting' --data 'format=json' >/dev/null; then
    if docker compose exec -T backend python manage.py shell -c 'from core.live_web import status; result=status(probe=True); assert result.get("reachable"), result; print(result)' >/dev/null; then
      echo "ForgeGov live web search is enabled."
      exit 0
    fi
  fi
  sleep 2
done

echo "SearXNG did not become ready. Run: docker compose logs searxng"
exit 1
