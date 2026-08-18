#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Tracked secret-bearing environment files"
tracked_env="$(git ls-files | grep -E '(^|/)\.env($|\.(production|prod|local|staging)$)' || true)"
if [ -n "$tracked_env" ]; then
  echo "FAIL: tracked environment file(s):"
  echo "$tracked_env"
  exit 1
fi
echo "PASS"

echo "Credential-like values in application source"
files="$(grep -RIlE \
  'sk-[A-Za-z0-9_-]{24,}|re_[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16}' \
  backend frontend \
  --exclude='*.md' --exclude='*.lock' --exclude='test*.py' --exclude='*test*.py' \
  --exclude-dir='node_modules' --exclude-dir='.next' --exclude-dir='__pycache__' \
  || true)"
if [ -n "$files" ]; then
  echo "FAIL: credential-like values found in:"
  echo "$files"
  exit 1
fi
echo "PASS"
