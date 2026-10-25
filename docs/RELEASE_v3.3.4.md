# ForgeGov v3.3.4 — Enforce subscription access

Unpaid legacy workspaces previously retained unlimited product access. Authentication never enforced the subscription contract. This release rejects protected API reads and writes for ineligible organizations through bearer JWT, cookie JWT, and Django session authentication. Existing sessions are checked on every request. There is no billing-disabled bypass.

Explicit recorded grandfathered exemptions remain permanent and provider-free. Company names, slugs, and a status label alone never grant an exemption. Existing Howard Dynamics and Strictly Hunter records are not modified. Paid subscriptions require an enabled platform plan, a manual or Stripe provider, and a future current-period end. Trials and delinquency grace require a future explicit expiry. Missing subscription records are created without product access.

The session response exposes a minimal entitlement boolean. The interface routes restricted workspaces to Billing and responds to server subscription-required errors after expiry. Billing recovery remains available, including non-admin guidance to contact the workspace administrator/support. Public marketing, account/security recovery, workspace switching, and authorized platform administration remain available. Payment success URLs never grant entitlement.

No schema or production subscription data migration. Existing stored data remains intact. The full-stack disposable QA workspace receives a one-day manual entitlement rather than bypassing enforcement. New tests use actual bearer/cookie/session authentication to exercise denial, paid expiry, recorded exemptions, name/status spoofing and workspace isolation.

Production preflight identified three exempt records (two Howard Dynamics, one Strictly Hunter) and one disabled-provider legacy record. The latter will be restricted by this release. Automated checkout configuration and actual payment processing must be verified separately; this change does not claim to activate payments or collect a charge.

Rollback baseline: 73a14014c1d4f356f3abdb6bba5aa6536ddf49f7 (v3.3.3). Rollback restores the old unpaid-access behavior; use only for a critical regression and retain awareness of that exposure.
