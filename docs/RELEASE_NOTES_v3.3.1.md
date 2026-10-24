# ForgeGov 3.3.1 — Layout consistency and workflow reliability

This maintenance release applies the accumulated experience-audit corrections
and fixes the billing and Microsoft 365 layout defects identified in the latest
production screenshots.

## Layout changes

- Shared panels own their content inset. Framed settings sections instead let
  their headers and rows own it, avoiding doubled padding.
- Mobile cards respect the shared spacing token rather than an overriding
  `!important` rule. Buttons wrap at word boundaries instead of splitting words.
- Teams destination controls occupy their own full-width row, have persistent
  accessible labels, and stack at smaller breakpoints. The save action keeps
  its complete label. Existing destination-save requests are preserved.
- Billing separates the plan description from its access metrics, aligns icons,
  keeps content inside card insets, and removes oversized empty measurement
  states. Exempt workspaces retain their existing payment restrictions.
- Feedback remains available at the end of the page instead of floating over
  card text and controls.
- The prior audit's dashboard, feed, report, room, proposal, pricing, source-link,
  theme and error-state corrections are included. Next.js remains at 16.4.2.

## Verification

CI runs backend and migration checks, source audit, frontend lint/typecheck/build,
production dependency audit, full-stack Docker persistence and backup/restore,
and the cross-browser responsive suites. The experience matrix now exercises
connected Teams settings and exempt billing with long text in both themes and
both density settings. Geometry assertions cover actual child insets, complete
button labels, control dimensions, and horizontal overflow. Teams saves use
isolated HTTP fixtures; no Microsoft messages or production defaults are sent.

Customer screenshots are private reference evidence and are not committed.
Generated synthetic screenshots are retained as CI artifacts for visual review.

## Release and rollback

Before merging, record the current production main revision and preserve it as
`rollback/pre-v3.3.1`. Tag the validated release `v3.3.1`. Verify all application
services, public health/readiness, branding, and authenticated geometry after
deployment. Roll back application services to the recorded pre-release revision
if production verification fails; do not restore or overwrite customer data.

No schema migration, production credential change, payment activation or change
to grandfathered subscription rules is introduced by the 3.3.1 layout changes.
Provider answer quality, Stripe sandbox completion, and legal review remain
separate commercial-activation checks; this UI release does not certify them.
