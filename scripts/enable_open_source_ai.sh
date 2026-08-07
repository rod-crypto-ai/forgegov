#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add required government-data credentials before production use."
fi

MODEL="${1:-qwen3:8b}"
BASE_URL="${OLLAMA_BASE_URL_OVERRIDE:-http://host.docker.internal:11434}"

python3 - "$MODEL" "$BASE_URL" <<'PY'
from pathlib import Path
import sys

model = sys.argv[1]
base_url = sys.argv[2]
path = Path('.env')
lines = path.read_text().splitlines()
updates = {
    'AI_PROVIDER': 'ollama',
    'OLLAMA_BASE_URL': base_url,
    'OLLAMA_MODEL': model,
}
for key, value in updates.items():
    for index, line in enumerate(lines):
        if line.startswith(key + '='):
            lines[index] = f'{key}={value}'
            break
    else:
        lines.append(f'{key}={value}')
path.write_text('\n'.join(lines) + '\n')
PY

echo "Switching ForgeGov AI to the self-hosted Ollama model: $MODEL"
docker compose up -d --force-recreate backend

echo "Checking Ollama from the ForgeGov backend container..."
if docker compose exec -T backend python - "$MODEL" <<'PY'
import os, sys, requests
base = os.getenv('OLLAMA_BASE_URL', '').rstrip('/')
model = sys.argv[1]
response = requests.get(base + '/api/tags', timeout=15)
response.raise_for_status()
models = [str(item.get('name') or '') for item in response.json().get('models', [])]
if not any(name == model or name.startswith(model + ':') or model.startswith(name + ':') for name in models):
    raise SystemExit(f'Ollama is reachable, but {model!r} is not installed. Available models: {models or "none"}')
print(f'Ollama is reachable and {model} is installed.')
PY
then
  echo "ForgeGov open-source AI is enabled."
else
  cat <<EOF2
ForgeGov was configured for Ollama, but the model check failed.
Install/start Ollama on the Mac, then run:
  ollama pull $MODEL
  ./scripts/enable_open_source_ai.sh "$MODEL"
EOF2
  exit 1
fi
