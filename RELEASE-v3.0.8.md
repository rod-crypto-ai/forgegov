# ForgeGov v3.0.8 — Data Integrity & Connector Resilience

## Release purpose
Protect ForgeGov from duplicate, stale, malformed, and temporarily unavailable upstream government data while preserving source history and provenance.

## Included
- Source-record fingerprints and version history for SAM.gov opportunities, Grants.gov opportunities, USAspending awards, and ingested opportunity documents.
- Stale-source regression protection when an upstream record is older than the stored authoritative version.
- Quarantine for malformed/unpersistable source records with occurrence counting and Platform Admin retry.
- Connector retry/backoff and shared-cache circuit breakers for SAM.gov, USAspending, Grants.gov, SBA SUBNet, acquisition forecast sources, and SearXNG.
- Integrity metrics in Platform Admin system operations.
- Existing unique source IDs/checksums remain the primary dedupe controls; v3.0.8 adds change-history evidence around them.
- Sync-run metadata records unchanged/quarantined counts.
- v3.0.8 regression tests and release verifier.

## Migration
`core.0027_data_integrity_connector_resilience` creates source version and quarantine tables.
