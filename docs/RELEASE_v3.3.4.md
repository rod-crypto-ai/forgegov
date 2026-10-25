# ForgeGov v3.3.4 — Subscription enforcement

Protected API reads and writes now check organization entitlement for bearer tokens, cookies, and Django sessions. Unpaid legacy access is rejected. Explicit recorded exemptions remain intact; names and status labels cannot grant exemptions. Paid access requires an eligible provider, enabled plan, and unexpired paid period. Trial and grace access require explicit future deadlines.

The UI routes restricted sessions to billing. Account recovery, billing recovery, workspace switching, and authorized platform administration remain available. No schema migration or customer data changes. Payment-provider activation is outside this patch.

Validation: 382 backend tests, frontend lint/typecheck/build, migration consistency, and release source audit passed locally. Browser CI covers restricted-session redirects and the existing billing layouts. Disposable QA receives a bounded manual entitlement.

Rollback baseline: 73a14014c1d4f356f3abdb6bba5aa6536ddf49f7. Rolling back restores the prior unpaid-access behavior.
