# ForgeGov v1.1.0

## Added
- Live SAM.gov Contract Awards API endpoint for federal contracts, IDVs, and contract vehicles.
- Active Awards navigation backed by live SAM data instead of empty local tables.
- Opportunity document metadata and protected-description retrieval endpoint.
- Contract vehicle opportunity page connected to live SAM opportunity search.
- Server-side setting for the SAM Contract Awards endpoint.

## Notes
- Federal forecasts remain source-by-source because no universal federal forecast API exists.
- State/local coverage still requires separate portal connectors or licensed aggregation.
- Opportunity documents are exposed as in-app metadata and links; durable storage, malware scanning, and text extraction remain later work.
