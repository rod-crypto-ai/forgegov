#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "3.1.1"
errors: list[str] = []


def require(condition: bool, message: str):
    if not condition:
        errors.append(message)


require((ROOT / "VERSION").read_text().strip() == EXPECTED, "VERSION is not 3.1.1")
package = json.loads((ROOT / "frontend/package.json").read_text())
require(package.get("version") == EXPECTED, "frontend package version is not 3.1.1")
require(f'VERSION = "{EXPECTED}"' in (ROOT / "backend/core/version.py").read_text(), "backend version is not 3.1.1")

# Historical migrations must never depend on a moving target.
for migration in ROOT.glob("backend/*/migrations/*.py"):
    text = migration.read_text(errors="ignore")
    require('"__latest__"' not in text and "'__latest__'" not in text, f"moving migration dependency in {migration.relative_to(ROOT)}")

# Private-beta production settings in the deployment blueprint.
render = (ROOT / "render.yaml").read_text()
for needle in (
    "PUBLIC_REGISTRATION_ENABLED\n    value: 'true'",
    "SECURE_SSL_REDIRECT\n    value: 'true'",
    "SECURE_HSTS_SECONDS\n    value: '31536000'",
    "REGISTRATION_MODE\n    value: public",
    "EMAIL_BACKEND\n    value: django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST_PASSWORD\n    sync: false",
):
    require(needle in render, f"Render production gate missing: {needle.splitlines()[0]}")

requirements = (ROOT / "backend/requirements.txt").read_text()
require("pypdf>=6.16.1,<7" in requirements, "pypdf security floor regressed")
require("cryptography>=50,<51" in requirements, "cryptography security floor regressed")

explorer = (ROOT / "frontend/components/opportunity-explorer.tsx").read_text()
states = (ROOT / "frontend/lib/us-states.ts").read_text()
require("US_STATE_OPTIONS" in explorer, "SAM opportunity State dropdown is not wired")
require('["TX", "Texas"]' in states and '["DC", "District of Columbia"]' in states, "State dropdown list is incomplete")
require("connectors are being added" not in explorer.lower(), "stale connector placeholder copy remains in opportunity explorer")
require("not configured yet" not in explorer.lower(), "opportunity explorer contains a launch-blocking not-configured message")

# User-facing launch blockers must not remain in active frontend source.
blockers = ("coming soon", "not configured yet", "connectors are being added", "mock live records")
for source in list((ROOT / "frontend/app").rglob("*.tsx")) + list((ROOT / "frontend/components").rglob("*.tsx")):
    text = source.read_text(errors="ignore").lower()
    for blocker in blockers:
        require(blocker not in text, f"launch-blocking frontend copy '{blocker}' in {source.relative_to(ROOT)}")

router = (ROOT / "frontend/app/[...slug]/page.tsx").read_text()
for workspace in ("ForecastWorkspace", "ContractVehicleWorkspace", "StateLocalWorkspace", "SubcontractWorkspace"):
    require(workspace in router, f"source-specific workspace route missing: {workspace}")

# Carry-forward regressions discovered during v3.0.8/v3.0.9 validation.
tests = (ROOT / "backend/core/tests.py").read_text()
require("from .version import VERSION as FORGEGOV_VERSION" in tests, "health tests are missing current-version import")
resilience = (ROOT / "backend/core/integration_resilience.py").read_text()
require('requests.get if method_name == "GET"' in resilience, "connector test-isolation fix is missing")
platform_migration = (ROOT / "backend/platform_admin/migrations/0001_initial.py").read_text()
require("0026_mfa_sessions_passkeys" in platform_migration, "platform_admin historical migration dependency regressed")

# v3.1.1 beta stabilization and public landing requirements.
landing = (ROOT / "frontend/components/public-landing.tsx").read_text()
require("Find the work. Understand the market. Run the capture." in landing, "public landing page hero is missing")
require("/auth/registration-config/" in landing, "landing page does not reflect runtime registration state")
auth_provider = (ROOT / "frontend/components/auth-provider.tsx").read_text()
require('pathname === "/"' in auth_provider, "root landing route is not public")
creator_permissions = (ROOT / "backend/platform_admin/permissions.py").read_text()
require("IsPlatformCreator" in creator_permissions and '"creator"' in creator_permissions, "creator role enforcement is missing")
creator_command = (ROOT / "backend/platform_admin/management/commands/promote_creator.py").read_text()
require("Creator access requires MFA" in creator_command, "creator bootstrap does not require MFA")
registration = (ROOT / "backend/core/registration_control.py").read_text()
require("effective_registration_mode" in registration, "runtime registration control is missing")
feedback = (ROOT / "frontend/components/beta-feedback.tsx").read_text()
require("/beta-feedback/" in feedback, "in-app beta feedback is not wired")

if errors:
    print("Private beta launch source audit FAILED:")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("Private beta launch source audit passed.")
