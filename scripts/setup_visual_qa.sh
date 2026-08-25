#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m venv .venv-visual-qa
. .venv-visual-qa/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-visual-qa.txt
python -m playwright install chromium firefox webkit
printf '\nVisual QA is ready. Run:\n  .venv-visual-qa/bin/python scripts/visual_qa_subcontracting.py\n'
