# ForgeGov v2.0.3 — Live Opportunity Intelligence Hotfix

## Packaging correction

- Uses npm-compatible semantic version `2.0.3`.
- Restores the clean dependency lockfile from v2.0.2.
- Prevents release version updates from modifying third-party dependency versions or registry URLs.

## Release focus

This release retains the v2.0.2 grant, subcontracting, interactive intelligence, and private live-web capabilities while correcting the SearXNG health-probe behavior found by the full Docker validation gate.

## Hotfix

- Explicit `probe=true` status checks now always perform a fresh SearXNG JSON search.
- Cached health data can no longer mask a current outage or bypass the integration test.
- Non-probe UI requests may reuse the latest successful health result for efficient status display.
- The SearXNG health cache key is versioned so stale v2.0.2 results do not carry into this release.
- Product identity is updated consistently to `2.0.3`.

## Included v2.0.2 capabilities

- Resilient SBA SUBNet discovery with official-source, indexed, cached, and stored-history fallbacks.
- Interactive contract, grant, award, agency, company, vehicle, and forecast routes.
- Full Grants.gov opportunity workspaces with details, eligibility, documents, pipeline actions, capture tools, timeline, and contextual AI.
- OpenAI or self-hosted Ollama support.
- Private SearXNG live web search with source-backed AI responses.

## Release gate

Run:

```bash
./scripts/validate_release.sh
```

Do not deploy unless all eight stages pass and the script ends with:

```text
ForgeGov v2.0.3 validation completed successfully.
```
