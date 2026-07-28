# ForgeGov v1.2.0 Validation Report

## Packaging-environment checks completed

- Python source compilation passed for `backend` and `scripts`.
- Bash syntax passed for installer, verifier, rollout, and backend entrypoint scripts.
- Frontend JSON metadata parsed successfully.
- TypeScript and TSX syntax transpilation passed for all frontend source files.
- Release routes, migration files, and v1.2.0 version markers were checked.
- The package contains 30 Django tests, including organization isolation, alert deduplication, opportunity details, contract vehicles, forecasts, subcontract data, and partner discovery.
- Official public-source locations were reviewed for Acquisition.gov forecasts, SBA SUBNet, SAM.gov acquisition subaward reporting, and USAspending.

## Required final validation on the target Mac

The packaging environment does not provide Docker or the project API keys. The included `VERIFY.command` therefore remains the authoritative release gate. It builds the containers, runs migrations and all Django tests, probes live SAM.gov and OpenAI access, runs frontend lint/type checks, builds the production frontend image, and checks local health endpoints.

Required final line:

```text
ForgeGov v1.2.0 verification passed.
```

Do not commit or deploy the release unless that line appears.
