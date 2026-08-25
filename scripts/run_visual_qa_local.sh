#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="forgegov-visual-qa-frontend:3.2.1.3"
CONTAINER="forgegov-visual-qa-frontend"
PORT="${FORGEGOV_QA_FRONTEND_PORT:-3100}"
BASE_URL="http://127.0.0.1:${PORT}"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "Building production-style frontend for visual QA..."
docker build \
  --target runner \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api \
  -t "$IMAGE" \
  ./frontend

echo "Starting isolated production-style frontend on ${BASE_URL}..."
docker run -d \
  --name "$CONTAINER" \
  -p "127.0.0.1:${PORT}:3000" \
  "$IMAGE" >/dev/null

ready=0
for _ in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/opportunities/subcontracting" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" != "1" ]; then
  echo "Visual-QA frontend did not become ready. Container logs:" >&2
  docker logs "$CONTAINER" >&2 || true
  exit 1
fi

echo "Running responsive QA against production-style Next.js runtime..."
FORGEGOV_QA_BASE_URL="$BASE_URL" \
  .venv-visual-qa/bin/python scripts/visual_qa_subcontracting.py

echo "Running interactive shell/tablet UX QA..."
FORGEGOV_QA_BASE_URL="$BASE_URL" \
  .venv-visual-qa/bin/python scripts/visual_qa_shell.py
