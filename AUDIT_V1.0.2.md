# ForgeGov v1.0.2 Audit

## Defects confirmed in v1.0.1

1. `OPENAI_API_KEY` was read nowhere in the backend, and the assistant frontend always returned a fixed placeholder. The key could not affect application behavior.
2. Federal contract and federal grant opportunity pages initially displayed an empty result state unless a user submitted a search or arrived through a special `auto=1` URL.
3. Restarting an existing Docker container did not reload changes made to `.env`; the container needed to be recreated.

## Corrections in v1.0.2

- Added a server-side OpenAI Responses API integration and authenticated `/api/ai/chat/` endpoint.
- Added bounded, organization-isolated grounding context.
- Added OpenAI status, model configuration, request throttling, and actionable upstream error handling.
- Replaced the assistant placeholder with a working API client, loading state, error display, and model status.
- Added automatic recent-data loading on SAM.gov and Grants.gov opportunity pages.
- Added newest-first ordering for the initial result page and preserved normal source ordering after filters are applied.
- Updated installation and verification scripts to recreate containers after environment changes.
- Added mocked OpenAI tests and a cross-workspace context-isolation test.

## Validation performed in the artifact environment

Passed:

- Python compilation for backend and scripts
- Shell syntax for installer, verifier, and entrypoint
- JSON parsing for package metadata and TypeScript configuration
- TypeScript/TSX transpilation syntax checks for the changed frontend files
- Static checks for endpoint registration, environment settings, and release contents

Not runnable in the artifact environment:

- Full Django tests because the external Python package index was unavailable
- Full `npm ci`, ESLint, and Next.js production build because the external npm registry was unavailable
- Live SAM.gov or OpenAI calls because user credentials are not available here
- Docker runtime validation because a Docker daemon is not exposed here

`VERIFY.command` performs these runtime checks on the user's Mac with the installed dependencies and local secrets.

## Remaining limitations

- File content extraction and semantic document retrieval are not implemented; the AI receives file metadata only.
- AI conversations are held in the browser session and are not stored as database conversation records.
- Federal forecast, federal vehicle, and state/local opportunity connectors remain unimplemented and do not display mock data.
