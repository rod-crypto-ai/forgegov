# Data Sources

## SAM.gov Get Opportunities Public API

ForgeGov uses the official production v2 opportunity-search endpoint. The API requires posted-from and posted-to dates, supports pagination, and returns the latest active version of each opportunity. ForgeGov stores the source notice ID and raw response to support idempotent updates and traceability.

Implementation rules:

- Store the API key only in `.env` locally or a deployment secret manager.
- Never expose the key through `NEXT_PUBLIC_*` variables or browser requests.
- Respect the account's daily rate limit.
- Use the official query parameter names rather than undocumented search parameters.
- Retain source links, source IDs, raw records, and synchronization history.
- Do not overwrite user-entered capture notes during government-data refreshes.

## USAspending API

Purpose: federal award, recipient, agency, and spending intelligence.

The current connector exposes configuration and an optional reachability probe. Full award ingestion belongs in a separate model and synchronization pipeline because blindly loading award data would create duplicates, poor aggregation, and an unusable database.

## Data integrity rules

- Never present predicted recompetes as official dates.
- Never silently merge organizations solely by similar names.
- Never invent contracting contacts or requirements.
- Display the government source and last-updated time on source records.
- Separate government-source fields from private capture data.
