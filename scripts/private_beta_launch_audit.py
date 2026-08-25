#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "3.2.1.3"
FRONTEND_EXPECTED = "3.2.1-3"
errors: list[str] = []


def require(condition: bool, message: str):
    if not condition:
        errors.append(message)


require((ROOT / "VERSION").read_text().strip() == EXPECTED, "VERSION is not 3.2.1.3")
require(not (ROOT / "INSTALL.command").exists(), "obsolete root INSTALL.command must be removed")
require(not (ROOT / "VERIFY.command").exists(), "obsolete root VERIFY.command must be removed")
package = json.loads((ROOT / "frontend/package.json").read_text())
require(package.get("version") == FRONTEND_EXPECTED, "frontend package version is not 3.2.1-3")
require(f'VERSION = "{EXPECTED}"' in (ROOT / "backend/core/version.py").read_text(), "backend version is not 3.2.1.3")

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

# v3.1.2 alerts, notifications, and daily intelligence requirements.
models = (ROOT / "backend/core/models.py").read_text()
for model_name in ("NotificationPreference", "NotificationDelivery"):
    require(f"class {model_name}" in models, f"notification model missing: {model_name}")
require("event_key = models.CharField" in models, "durable alert event deduplication key is missing")

tasks = (ROOT / "backend/core/tasks.py").read_text()
for task_name in (
    "evaluate_opportunity_change_alerts",
    "evaluate_deadline_alerts",
    "send_daily_intelligence_digests",
    "send_weekly_intelligence_digests",
):
    require(f"def {task_name}" in tasks, f"scheduled notification task missing: {task_name}")

notification_helpers = (ROOT / "backend/core/notifications.py").read_text()
require("platform_notifications_enabled" in notification_helpers, "Creator notification kill switch is missing")
require("NotificationDelivery.objects.create" in notification_helpers, "tracked email delivery is missing")
require("notify_project_room_participants" in notification_helpers, "Project Room participant notification routing is missing")

urls = (ROOT / "backend/core/urls.py").read_text()
require('path("notifications/preferences/", notification_preferences)' in urls, "notification preference API route is missing")
require('path("notifications/deliveries/", notification_delivery_history)' in urls, "notification delivery history API route is missing")

admin_urls = (ROOT / "backend/platform_admin/urls.py").read_text()
require('path("notifications/", views.notification_operations)' in admin_urls, "platform notification operations route is missing")
require('path("notifications/test/", views.notification_test)' in admin_urls, "Creator notification test route is missing")
admin_views = (ROOT / "backend/platform_admin/views.py").read_text()
require('@permission_classes([IsPlatformCreator])\ndef notification_operations' in admin_views, "notification delivery operations must be Creator-only")
require('@permission_classes([IsPlatformCreator])\ndef notification_test' in admin_views, "notification test delivery must be Creator-only")

settings = (ROOT / "backend/forgegov/settings.py").read_text()
require("send-daily-intelligence-digests" in settings, "daily intelligence digest schedule is missing")
require("send-weekly-intelligence-digests" in settings, "weekly intelligence digest schedule is missing")
require('"schedule": 60 * 60' in settings, "hourly alert evaluation schedule is missing")

notification_page = (ROOT / "frontend/app/notifications/page.tsx").read_text()
for needle in ("/notifications/preferences/", "/notifications/deliveries/", "/alerts/"):
    require(needle in notification_page, f"unified notification center missing integration: {needle}")

admin_page = (ROOT / "frontend/app/platform-admin/page.tsx").read_text()
require("Send test to me" in admin_page, "Creator notification test control is missing")
require("Pause notifications" in admin_page, "Creator notification pause control is missing")

render = (ROOT / "render.yaml").read_text()
require(render.count("NOTIFICATION_DIGESTS_ENABLED") >= 2, "Render web/beat notification digest settings are incomplete")
require("envVarKey: EMAIL_HOST_PASSWORD" in render, "worker SMTP secret forwarding is missing")

# v3.1.3 capture intelligence and competitive positioning requirements.
require("class CompetitivePositionSnapshot" in models, "competitive-position snapshot model is missing")
positioning = (ROOT / "backend/core/competitive_positioning.py").read_text()
for needle in ("agency_buying_history", "competitor_profiles", "win_themes", "questions_to_validate", "qualification"):
    require(needle in positioning, f"competitive-positioning engine missing: {needle}")
require("official_historical_award_rollup" in positioning, "agency buying history lacks official-evidence classification")
require("not an official bidder list" in positioning, "competitor inference guardrail is missing")
require("does not have enough validated" in positioning.lower(), "win-theme evidence guardrail is missing")
require('path("ai/opportunities/<str:source_id>/competitive-positioning/", opportunity_competitive_positioning)' in urls, "competitive-positioning API route is missing")
command_center = (ROOT / "backend/core/capture_command_center.py").read_text()
require('"competitive_positioning": competitive' in command_center, "Capture Command Center does not include competitive positioning")
command_ui = (ROOT / "frontend/components/capture-command-center.tsx").read_text()
for needle in ("QUALIFICATION", "AGENCY BUYING HISTORY", "COMPETITOR DOSSIERS", "WIN THEMES"):
    require(needle in command_ui, f"Capture Command Center UI missing: {needle}")
vendor_profile = (ROOT / "frontend/app/participants/vendors/profile/page.tsx").read_text()
require("COMPETITIVE PROFILE" in vendor_profile, "vendor profile lacks competitive-history panel")
require("award_vendor =" in (ROOT / "backend/core/views.py").read_text(), "award-history-only competitors cannot resolve to vendor intelligence")
require("/participants/vendors/profile?name=" in command_ui, "competitor dossiers do not link to unified vendor profiles")
require((ROOT / "backend/core/migrations/0031_capture_competitive_positioning.py").exists(), "v3.1.3 competitive-positioning migration is missing")


# v3.2.0 ForgeAI Capture Copilot + Settings Center requirements.
require("class UserPreference" in models, "persistent user preference model is missing")
for field in ("theme", "density", "reduce_motion", "sidebar_collapsed", "ai_response_style", "ai_live_web_enabled", "ai_workspace_grounding_enabled"):
    require(field in models, f"user preference field missing: {field}")
require("contains_financial = models.BooleanField" in models, "Copilot analysis financial-scope marker is missing")
require("uses_workspace_context = models.BooleanField" in models, "Copilot workspace-context marker is missing")
require((ROOT / "backend/core/migrations/0032_capture_copilot_user_preferences.py").exists(), "v3.2.0 settings/Copilot migration is missing")

copilot = (ROOT / "backend/core/capture_copilot.py").read_text()
for needle in ("build_capture_copilot_brief", "run_capture_copilot", "include_financial", "workspace_grounding_enabled", "created_by=user", "contains_financial=include_financial", "uses_workspace_context=include_workspace"):
    require(needle in copilot, f"Capture Copilot security/runtime requirement missing: {needle}")
require("Financial context is excluded" in copilot, "Copilot financial-context redaction is missing")
require("Private ForgeGov workspace records were excluded" in copilot, "Copilot private-workspace grounding guard is missing")
ai_source = (ROOT / "backend/core/ai.py").read_text()
require("include_financial: bool = False" in ai_source, "general ForgeGov AI grounding does not default to financial redaction")
require("_user_can_read_financial" in ai_source, "general ForgeGov AI lacks financial-role grounding enforcement")
require('path("ai/opportunities/<str:source_id>/capture-copilot/", opportunity_capture_copilot)' in urls, "Capture Copilot API route is missing")
require('path("settings/preferences/", user_preferences)' in urls, "persistent settings API route is missing")
views = (ROOT / "backend/core/views.py").read_text()
require('history = history.filter(contains_financial=False)' in views, "Copilot history does not hide prior financial analyses from non-financial roles")
require('created_by=request.user' in views, "Copilot analysis history is not user-scoped")

theme_provider = (ROOT / "frontend/components/theme-provider.tsx").read_text()
for needle in ("system", "light", "dark", "forgegov-ui-preferences", "dataset.theme", "dataset.density"):
    require(needle in theme_provider, f"theme provider requirement missing: {needle}")
settings_page = (ROOT / "frontend/app/settings/page.tsx").read_text()
for needle in ("Appearance", "ForgeGov AI & Capture Copilot", "Notifications", "Account & workspace", "Security"):
    require(needle in settings_page, f"Settings Center section missing: {needle}")
copilot_ui = (ROOT / "frontend/components/capture-copilot.tsx").read_text()
require("FORGEAI CAPTURE COPILOT · v3.2.1" in copilot_ui, "Capture Copilot UI release identity is missing")
require('brief.economics.restricted?"Restricted"' in copilot_ui, "Capture Copilot UI does not honor financial redaction")
opportunity_page = (ROOT / "frontend/app/opportunities/federal-contracts/[noticeId]/page.tsx").read_text()
require("Capture Copilot" in opportunity_page and '"copilot"' in opportunity_page, "opportunity workspace Capture Copilot tab is missing")
layout = (ROOT / "frontend/app/layout.tsx").read_text()
require("ThemeProvider" in layout, "app-wide ThemeProvider is missing")
regression = (ROOT / "backend/core/test_v320_capture_copilot_settings.py").read_text()
for needle in ("financial_context_is_redacted", "private_workspace_grounding_preference", "history_is_hidden_after_role_loses_financial_access"):
    require(needle in regression, f"v3.2.0 security regression coverage missing: {needle}")


# v3.2.1 Proposal Automation + Production Live Web requirements.
for model_name in ("ProposalVolume", "ProposalSection", "ProposalSectionRequirement", "ProposalSectionRevision", "ProposalLibraryEntry"):
    require(f"class {model_name}" in models, f"v3.2.1 proposal production model missing: {model_name}")
require((ROOT / "backend/core/migrations/0033_proposal_automation_live_web.py").exists(), "v3.2.1 proposal production migration is missing")
proposal_automation = (ROOT / "backend/core/proposal_automation.py").read_text()
for needle in ("ensure_proposal_production", "draft_section", "package_validation", "save_section_revision", "VALIDATION REQUIRED"):
    require(needle in proposal_automation, f"proposal automation engine missing: {needle}")
require("Financial authorization is required to draft the pricing proposal section" in proposal_automation, "proposal pricing AI drafting is not financial-role gated")
require('path("ai/opportunities/<str:source_id>/proposal-production/", opportunity_proposal_production)' in urls, "proposal production API route is missing")
require('proposal-package-validation/' in urls and 'proposal-sections/<int:section_id>/revisions/' in urls, "proposal validation/revision routes are missing")
proposal_ui = (ROOT / "frontend/components/proposal-workspace.tsx").read_text()
for needle in ("PROPOSAL AUTOMATION + PRODUCTION", "Requirement traceability", "Evidence-grounded ForgeAI draft", "Proposal library", "VERSION HISTORY"):
    require(needle in proposal_ui, f"proposal production UI missing: {needle}")

live_web_source = (ROOT / "backend/core/live_web.py").read_text()
for needle in ('"live"', '"degraded"', '"unavailable"', '"not_configured"', "cached_fallback_available", "resilient_request"):
    require(needle in live_web_source, f"production live-web service missing: {needle}")
require('path("live-web/status/", live_web_status_view)' in urls, "live-web status API route is missing")
require('path("live-web/search/", live_web_search_view)' in urls, "live-web search API route is missing")
require('path("live-web/test/", views.live_web_test)' in admin_urls, "Creator live-web test route is missing")
require('@permission_classes([IsPlatformCreator])\ndef live_web_test' in admin_views, "Creator live-web test is not Creator-only")
require("type: pserv\n  name: forgegov-searxng" in render, "Render private SearXNG service is missing")
require("property: hostport" in render and "SEARXNG_HOSTPORT" in render, "Render private SearXNG host wiring is missing")
searx_settings = (ROOT / "searxng/settings.yml").read_text()
require("- json" in searx_settings, "SearXNG JSON search output is not enabled")
require((ROOT / "searxng/Dockerfile").exists(), "SearXNG private-service Dockerfile is missing")
require("live_web_search(" in (ROOT / "backend/core/integrations.py").read_text(), "SBA web fallback is not routed through shared live-web service")
require("Live Web Connected" in (ROOT / "frontend/components/assistant-workspace.tsx").read_text(), "explicit live-web connected state is missing from ForgeAI UI")
require("Live Web Unavailable" in (ROOT / "frontend/components/dashboard-home.tsx").read_text(), "explicit live-web unavailable state is missing from dashboard")

# v3.2.1 release-hardening: approval integrity, pricing boundaries, and web-query privacy.
require('can_approve: bool = False' in proposal_automation, "proposal production lacks explicit approval authority")
require('Proposal approval authority is required to approve or lock a section' in proposal_automation, "proposal section approval gate is missing")
require('links = [] if restricted' in proposal_automation, "restricted pricing requirement traceability is not hidden")
require('pricing_entry' in proposal_automation and 'if pricing_entry and not can_financial' in proposal_automation, "restricted pricing library content is not filtered")
require('Proposal approval authority is required to approve reusable content' in views, "reusable proposal content approval gate is missing")
require('substantive_change and entry.status == ProposalLibraryEntry.Status.APPROVED' in views, "approved reusable content is not invalidated after edits")
require('"permissions": {"can_financial": can_financial, "can_approve": can_approve}' in proposal_automation, "proposal workspace does not expose safe capability flags")
require('Link requirement' in proposal_ui and 'Approve for reuse' in proposal_ui, "proposal UI lacks traceability/approval controls")
require('web_query: str | None = None' in ai_source, "AI layer cannot separate private prompts from public web queries")
require('web_query=public_web_query' in proposal_automation, "proposal drafting does not use a sanitized live-web query")
require('web_query=public_web_query' in copilot, "Capture Copilot does not use a sanitized live-web query")
require('SEARXNG_URL = (f"http://{SEARXNG_HOSTPORT}" if SEARXNG_HOSTPORT else' in settings, "Render private SearXNG host does not take precedence over manual URL")
api_render_block = render.split('- type: web\n  name: forgegov-api', 1)[1].split('- type: worker\n  name: forgegov-worker', 1)[0] if '- type: web\n  name: forgegov-api' in render else ''
require('SEARXNG_URL' not in api_render_block, "Render API blueprint still defines a manual SEARXNG_URL that can override private-service wiring")
require('searxng/searxng:2026.8.17-374939b88' in (ROOT / "searxng/Dockerfile").read_text(), "production SearXNG image is not pinned")
require('searxng/searxng:2026.8.17-374939b88' in (ROOT / "docker-compose.yml").read_text(), "local SearXNG image does not match the pinned production version")
require('LIVE_WEB_SEARCH_RATE' in settings and 'LiveWebSearchThrottle' in (ROOT / "backend/core/throttles.py").read_text() and 'from .throttles import LiveWebSearchThrottle' in views, "direct live-web API rate limiting is missing or not imported")
require('Run live-web test' in admin_page, "Creator Live Web test control is missing")
require('payload["live_web"] = live_web_status(probe=True)' in admin_views, "Platform system operations do not expose Live Web health")

# v3.2.1.1 Microsoft 365 Connected Apps + subcontract parity + responsive UX.
require("class ConnectedApp" in models, "Connected Apps persistence model is missing")
require((ROOT / "backend/core/migrations/0034_connected_apps.py").exists(), "v3.2.1.1 Connected Apps migration is missing")
microsoft_graph = (ROOT / "backend/core/microsoft_graph.py").read_text()
for needle in ("code_challenge_method", "S256", "encrypt_secret", "decrypt_secret", "Mail.Send", "Calendars.ReadWrite", "ChannelMessage.Send", "Team.ReadBasic.All", "Channel.ReadBasic.All"):
    require(needle in microsoft_graph, f"Microsoft 365 least-privilege/OAuth requirement missing: {needle}")
require("workspace access changed before Microsoft authorization completed" in microsoft_graph, "Microsoft OAuth callback does not re-check ForgeGov workspace access")
require('path("integrations/microsoft/status/", microsoft_status)' in urls, "Microsoft Connected Apps status route is missing")
require('path("integrations/microsoft/verify/", microsoft_verify)' in urls, "Microsoft live verification route is missing")
require('"verified_at": timezone.now().isoformat()' in microsoft_graph, "Microsoft callback does not record live verification metadata")
require('def verify_connection(row: ConnectedApp)' in microsoft_graph, "Microsoft saved-connection verification service is missing")
require('path("integrations/microsoft/send-mail/", microsoft_send_mail)' in urls, "Outlook send route is missing")
require('path("integrations/microsoft/calendar-event/", microsoft_create_event)' in urls, "Outlook Calendar route is missing")
require('path("integrations/microsoft/teams-message/", microsoft_send_teams)' in urls, "Teams send route is missing")
require("MICROSOFT_CLIENT_SECRET" in render and "sync: false" in render, "Microsoft client secret is not externalized in Render")
require("MICROSOFT_CLIENT_SECRET=" in (ROOT / ".env.example").read_text(), "Microsoft deployment variables are not documented")
settings_page = (ROOT / "frontend/app/settings/page.tsx").read_text()
for needle in ("Connected Apps", "Microsoft 365", "Default Teams destination", "Connect Microsoft 365", "Microsoft 365 connected and verified", "Microsoft 365 connection failed"):
    require(needle in settings_page, f"Settings Connected Apps UI missing: {needle}")
ms_actions = (ROOT / "frontend/components/microsoft-actions.tsx").read_text()
for needle in ("Outlook email", "Calendar", "Teams", "ForgeGov never exposes your Microsoft access token", "Checking Microsoft 365 connection"):
    require(needle in ms_actions, f"Microsoft opportunity action UI missing: {needle}")
subcontract_source = (ROOT / "backend/core/subcontract_intelligence.py").read_text()
for needle in ("prime_contractor", "parent_contract_candidates", "official_historical_award_intelligence", "PipelineItem.objects.filter(organization=organization"):
    require(needle in subcontract_source, f"Subcontract workspace intelligence missing/isolation regressed: {needle}")
require('path("live/sba/subnet/<path:source_id>/", subcontract_workspace_detail)' in urls, "detailed SUBNet workspace API route is missing")
subcontract_page = ROOT / "frontend/app/opportunities/subcontracting/[sourceId]/page.tsx"
require(subcontract_page.exists(), "detailed subcontract opportunity workspace page is missing")
if subcontract_page.exists():
    subcontract_ui = subcontract_page.read_text()
    for needle in ("Prime & parent contract", "Capture intelligence", "Collaboration", "MicrosoftActions"):
        require(needle in subcontract_ui, f"subcontract workspace UI missing: {needle}")
responsive_css = (ROOT / "frontend/app/globals.css").read_text()
for needle in ("@media(max-width:1280px)", "@media(max-width:1080px)", "@media(max-width:900px)", "@media(max-width:680px)", "@media(max-width:430px)", "overflow-wrap:anywhere"):
    require(needle in responsive_css, f"responsive congestion-system requirement missing: {needle}")
regression_3211 = (ROOT / "backend/core/test_v3211_integrations_ux.py").read_text()
for needle in ("test_microsoft_status_is_user_scoped_and_does_not_expose_tokens", "test_microsoft_real_callback_persists_verified_connection", "test_microsoft_verify_marks_existing_connection_verified", "test_viewer_cannot_send_external_microsoft_actions", "test_subcontract_capture_context_is_workspace_isolated"):
    require(needle in regression_3211, f"v3.2.1.1 regression coverage missing: {needle}")

if errors:
    print("Private beta launch source audit FAILED:")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("Private beta launch source audit passed.")
