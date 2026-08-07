# ForgeGov v2.7.0-M2 — Award Intelligence & Connector SDK

## Delivered
- Incremental USAspending award ingestion with bounded page and date filters.
- Normalized federal award enrichment for parent awards, offices, CAGE, set-aside, jurisdiction, and source freshness.
- Award sync-run history and operational counts.
- Evidence-backed past-winner and likely-incumbent summaries.
- Connector SDK with capability, jurisdiction, authentication, licensing, rate-limit, and health metadata.
- USAspending federal award connector.
- Texas SmartBuy reference connector that remains disabled until an approved machine-readable feed is configured.
- Award Intelligence workspace and responsive layouts.
- New migration `0017_award_ingestion_connector_sdk`.

## Important limitation
Texas is a connector reference, not a live ingestion claim. ForgeGov will not scrape or redistribute Texas portal data until an approved API, export, or licensed feed and its terms are verified.
