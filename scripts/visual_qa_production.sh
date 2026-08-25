#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv-visual-qa/bin/python ]; then
  echo "Visual QA environment missing. Run ./scripts/setup_visual_qa.sh first." >&2
  exit 1
fi
export FORGEGOV_QA_BASE_URL="${FORGEGOV_QA_BASE_URL:-https://forge-gov.com}"
export FORGEGOV_QA_ARTIFACT_DIR="${FORGEGOV_QA_ARTIFACT_DIR:-$ROOT/artifacts/visual-qa-production}"
exec .venv-visual-qa/bin/python scripts/visual_qa_subcontracting.py
