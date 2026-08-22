# ForgeGov v3.2.0 — ForgeAI Capture Copilot + Settings Center

## Release goal

Turn the capture intelligence built through v3.1.3 into an actionable, evidence-grounded Copilot while adding a real persistent Settings Center for appearance, AI behavior, notifications, account/workspace navigation, and security.

## ForgeAI Capture Copilot

- Adds a dedicated Capture Copilot tab to federal opportunity workspaces.
- Builds a deterministic capture brief before any model call so ForgeGov remains useful when the AI provider is unavailable.
- Supports executive review, bid/no-bid challenge, customer strategy, competitor review, proposal strategy, red-team review, next actions, and free-form pursuit questions.
- Grounds recommendations in current ForgeGov opportunity, capture, competitive-positioning, and authorized workspace evidence.
- Separates historical competitor/incumbent signals from confirmed bidder facts.
- Persists and safely reuses user-scoped Copilot analyses when the evidence and AI settings have not changed.

## AI privacy and financial controls

- Copilot economics are available only to roles with existing `financial_read` capability.
- Non-financial users receive a redacted economics object and no raw capture-memory payload in Copilot.
- Copilot cache fingerprints include user identity, financial scope, workspace-grounding state, response style, and live-web preference.
- Copilot history is user-scoped and hides analyses that contain financial context after financial access is removed.
- General ForgeGov AI grounding now omits workspace `estimated_value` fields unless the current workspace role has financial access.
- Disabling private workspace grounding excludes private workspace context from new generic AI and Capture Copilot requests.

## Settings Center

New `/settings` experience with persistent per-user preferences:

- Theme: System, Light, Dark.
- Interface density: Comfortable or Compact.
- Reduce motion.
- Start with sidebar collapsed.
- AI response depth: Concise, Balanced, Detailed.
- Live web research enable/disable.
- Private workspace grounding enable/disable.
- Core notification delivery controls and intelligence digest cadence.
- Links to personal/company profile, Company Hub, team administration where authorized, Security Center, MFA/passkeys/sessions, and password recovery.

Appearance preferences are applied at the root application level and stored both locally for fast paint and server-side for authenticated persistence.

## Data model

Migration `core.0032_capture_copilot_user_preferences`:

- creates `UserPreference`;
- adds Capture Copilot as an `OpportunityAnalysis` analysis type;
- adds `contains_financial` and `uses_workspace_context` scope markers to persisted AI analyses.

## Validation

`VERIFY_V3.2.0.command` runs the 21-stage release gate, including the dedicated v3.2.0 Copilot/settings/security regression suite. Do not push or tag until all 21 stages pass locally.
