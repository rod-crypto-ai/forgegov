# ForgeGov v3.2.1.1 — Integration & UX Refinement

v3.2.1.1 is a focused stabilization/enhancement release inserted before v3.2.2. It does not change the primary product roadmap. It addresses three platform-level issues that were intentionally prioritized after v3.2.1: Microsoft 365 integration, subcontracting opportunity-workspace parity, and cross-device layout congestion.

## Microsoft 365 Connected Apps

ForgeGov now has a server-side Connected Apps foundation and a Microsoft 365 provider.

### Security model
- OAuth 2.0 authorization-code flow with PKCE.
- Delegated Microsoft Graph permissions only.
- One-time OAuth state stored for ten minutes.
- Workspace membership is revalidated when the Microsoft callback completes.
- Access and refresh tokens are encrypted at rest using ForgeGov's existing application encryption key.
- Tokens are never returned to the browser.
- Connections are scoped to one ForgeGov user + company workspace.
- Viewer accounts cannot send external messages or create calendar events.
- Disconnecting removes the locally stored Microsoft access/refresh tokens.

### Initial Microsoft capabilities
- Outlook email (`Mail.Send`).
- Outlook Calendar events (`Calendars.ReadWrite`).
- Microsoft Teams channel messages (`ChannelMessage.Send`).
- Joined Team discovery (`Team.ReadBasic.All`).
- Channel discovery (`Channel.ReadBasic.All`).

Settings → Connected Apps lets each user connect their Microsoft account and choose a default Team/channel. Federal contract and subcontract workspaces expose one compact Microsoft 365 action rather than adding multiple permanent header buttons.

## Subcontracting Opportunity Workspace 2.0

SBA SUBNet remains the live discovery source, but each indexed subcontract opportunity now opens into a full ForgeGov workspace.

The workspace includes:
- complete listing description and source provenance;
- closing date, performance start, NAICS, and place of performance;
- parsed prime point-of-contact information;
- prime contractor vendor-profile bridge;
- historical public prime award rollup;
- possible parent-contract/reference candidates, explicitly labeled as evidence or inference;
- current company-specific Pipeline state;
- Add to Pipeline and capture links;
- ForgeAI subcontract capture analysis;
- Microsoft Outlook/Calendar/Teams collaboration actions;
- Project Room and ForgeGov Network entry points.

Pipeline data remains company isolated. Historical award evidence never proves current bidder intent or a parent-contract relationship without verification.

## Responsive UI / congestion overhaul

The UI now applies a stronger responsive contract across the application rather than relying on page-by-page fixes:
- cards and headers use `min-width: 0` and safe wrapping;
- long opportunity titles, solicitation numbers, companies, and source text wrap rather than crush adjacent controls;
- action groups wrap and collapse cleanly;
- wide tables preserve horizontal scrolling rather than compressing columns into unreadable widths;
- settings navigation scrolls horizontally on narrow layouts;
- workspace tab rails remain scrollable;
- two-column intelligence layouts stack before they become congested;
- phone action bars become one/two-column layouts;
- Microsoft actions are consolidated behind one entry point;
- dedicated breakpoints cover 1280, 1080, 900, 680, and 430px layouts.

The release gate still requires the normal frontend lint, TypeScript, and production build stages. Manual acceptance should additionally inspect 390, 768, 1024, 1280, 1440, and 1920px widths plus 125% and 150% browser zoom.

## Migration

`core.0034_connected_apps`

## Release identity

ForgeGov application/release version: `3.2.1.1`

The frontend package uses valid npm SemVer `3.2.1-1` because npm does not accept four numeric version components.

## Validation

Run `VERIFY_V3.2.1.1.command`. The 24-stage gate includes all historical suites, the v3.2.1 proposal/live-web regression suite, the new Microsoft/subcontract/UX regression suite, real Live Web connectivity, frontend lint/type/build, dependency/security audits, non-root runtime validation, isolated database restore, and final health/readiness.
