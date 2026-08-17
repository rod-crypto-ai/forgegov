#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000/api}"
EXPECTED_VERSION="${EXPECTED_VERSION:-$(cat VERSION)}"
python3 - "$BASE_URL" "$EXPECTED_VERSION" <<'PY'
import json, sys, urllib.request
base, expected = sys.argv[1].rstrip('/'), sys.argv[2]
for name in ("health", "ready"):
    with urllib.request.urlopen(f"{base}/{name}/", timeout=20) as response:
        data = json.load(response)
    if data.get("version") != expected:
        raise SystemExit(f"{name}: expected version {expected}, got {data.get('version')}")
    if name == "health" and data.get("status") != "ok":
        raise SystemExit(f"health failed: {data}")
    if name == "ready" and data.get("status") != "ready":
        raise SystemExit(f"readiness failed: {data}")
    print(name, data)
PY
