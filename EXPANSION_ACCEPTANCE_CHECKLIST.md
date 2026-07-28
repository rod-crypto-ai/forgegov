# ForgeGov v1.2.0 Expansion Acceptance Checklist

## Automated release gate

Run:

```bash
cd ~/Documents/GitHub/forgegov
./VERIFY.command
```

Required final result:

```text
ForgeGov v1.2.0 verification passed.
```

## Functional checks

- Federal contracts load current SAM.gov records.
- Opportunity detail opens the SAM source, description, and public attachments.
- Add-to-pipeline creates an organization-scoped pipeline item.
- Incumbent signals are labeled as inferred candidates, not confirmed incumbents.
- Contract Vehicles returns USAspending IDV records and persists selected results.
- Federal Forecasts opens current agency forecast sources from Acquisition.gov.
- Subcontracting returns SBA SUBNet listings and SAM acquisition subaward records.
- Teaming discovery filters stored vendors and creates draft teaming leads.
- Agency and vendor profiles summarize stored award intelligence.
- NAICS and PSC analytics aggregate stored awards and opportunities.
- Saved-search evaluation creates deduplicated alerts only for the current organization.
- Alert PATCH operations can change only read/dismissed state.
- State/local sources open verified public procurement portals without presenting mock records.

## Production checks

- API, worker, and beat use the same database, Redis URL, Django secret, and SAM key.
- Django migrations complete before traffic is accepted.
- The frontend points to the production `/api` URL.
- CORS and CSRF origins exactly match the frontend domain.
- No `.env`, secret keys, runtime Celery database files, `.next`, or `node_modules` are committed.
