# ForgeGov v3.3.6

Saved SAM.gov opportunity continuity

- Keep saved opportunity and pipeline workspaces accessible when a live SAM.gov lookup is empty or unavailable. Use a saved notice's posted date for its lookup instead of limiting it to the latest 30 days.
- Clearly disclose saved-record fallback and its save timestamp. Require users to verify amendments, status, and deadlines at SAM.gov before acting. Never label the fallback as live.
- Preserve stored descriptions and attachment metadata when the provider key or service is unavailable. Match the requested notice identifier and source exactly; unknown notices still fail.
- Regression coverage includes pipeline continuity, upstream failures, live-record precedence, identifier/source mismatch, and rendered fallback disclosure across the existing responsive browser matrix.

Production checks before this release confirmed sign-in, seven live source probes, and founding-workspace billing access. A bounded manual USAspending run processed 300 records in about 18 seconds and created 113 awards; it correctly reported partial because its three-page cap was reached. This is not proof of a complete scheduled ingestion window. Historical timeout-run reconciliation, production payment completion, and delivered email remain separate verification gaps.

Rollback revision is ce23bd9b493316d87dca432aed30013051179432 (v3.3.5). No schema, permission, subscription, or payment-provider changes are included.
