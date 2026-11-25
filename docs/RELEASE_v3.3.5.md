# ForgeGov v3.3.5

## Platform quality and recovery

- Mount the workspace shell only on workspace pages. Public pages avoid private notification and invitation polling. Switching organizations remounts the shell and its page state.
- Keep mobile navigation keyboard focus inside the open drawer, dismiss it with Escape, restore focus to its trigger, and expose expanded navigation sections and current links to assistive technology.
- Increase mobile public-navigation, source-disclosure, caption, and product-tour text sizes and navigation touch targets at their source styles.
- Initialize theme state consistently between server rendering and client hydration, then restore local and account preferences. Hydrate the public homepage before switching it to an authenticated dashboard, including when session loading wins the initial-render race.
- Return structured API errors for ForgeAI provider failures, including briefing generation. Failed generations do not create empty analyses and can be retried.
- Update Next.js and its ESLint integration from 16.4.2 to 16.4.6 to incorporate published security fixes. Use the browser container's native Python with verified TLS support in responsive CI.
- Avoid rewriting unchanged USAspending awards and recalculating vendor and agency summaries on every repeated record. Refresh each affected agency once after the ingestion batch. Preserve source observation history and changed-record ingestion.
- Give scheduled USAspending ingestion a soft deadline before the worker's hard termination. Retain committed records and finish the run with an explicit partial or failed state when interrupted.

## Validation and boundaries

Release acceptance uses the existing backend, frontend, Docker, full-stack, and Chromium/Firefox/WebKit CI gates. Regression coverage includes provider outage and recovery, repeat award ingestion, interrupted ingestion, public-page request isolation, and mobile drawer keyboard behavior.

Local browser checks use synthetic records and cover desktop, tablet, phone, light and dark themes. They exercise forms, source switches, proposal editing, Project Rooms, billing, and Microsoft 365 destination controls. They do not establish live provider availability, delivery of real customer email, or completed production payments.

Production verification must check the deployed version, readiness, public routes, and worker logs. USAspending recovery requires an observed completed live sync before it can be reported as resolved. Historical runs left running by older hard timeouts require an explicit recovery operation with a verified cutoff.

Rollback revision is e09afb370ffad79705c6ff765702263742162678, the v3.3.4 release. No schema changes are included.
