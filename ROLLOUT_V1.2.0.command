#!/bin/bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$HOME/Documents/GitHub/forgegov"

cd "$PACKAGE_DIR"
chmod +x INSTALL.command VERIFY.command backend/entrypoint.sh

printf '\n=== ForgeGov v1.2.0 installation ===\n'
./INSTALL.command

printf '\n=== ForgeGov v1.2.0 release verification ===\n'
cd "$PROJECT"
chmod +x VERIFY.command
./VERIFY.command

printf '\nForgeGov v1.2.0 is installed and locally verified.\n'
printf 'Next: review git status, commit, push main, then sync the Render Blueprint.\n'
