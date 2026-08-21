#!/usr/bin/env bash
set -euo pipefail

echo "Tracked secret-bearing environment files"

ENV_FILES="$(git ls-files | grep -E '(^|/)\.env($|\.(production|prod|local|staging)$)' || true)"

if [ -n "$ENV_FILES" ]; then
  echo "FAIL: tracked environment files found:"
  echo "$ENV_FILES"
  exit 1
fi

echo "PASS"
echo "Credential-like values in tracked production source"

MATCHES="$(
  git grep -nE '(^|[^A-Za-z0-9_])(sk-[A-Za-z0-9_-]{20,}|re_[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' -- backend frontend 2>/dev/null \
  | grep -Ev '(^|/)(test[^/]*\.py|tests\.py):' \
  || true
)"

if [ -n "$MATCHES" ]; then
  echo "FAIL: possible credentials found:"
  echo "$MATCHES"
  exit 1
fi

echo "PASS"
