# ForgeGov v1.0.2 — OpenAI and Recent Opportunity Data

## Fixed: OpenAI key had no effect

The v1.0.1 interface did not contain any backend OpenAI request code. Adding `OPENAI_API_KEY` could not make the assistant work because the assistant component always returned a placeholder message.

v1.0.2 adds:

- `POST /api/ai/chat/`
- Server-side OpenAI Responses API requests
- Configurable model and API base URL
- API-key, permissions, model, billing/rate-limit, timeout, and empty-response error messages
- OpenAI configuration visibility through `/api/integrations/status/`
- Per-user throttling
- Tenant-safe workspace grounding
- Inline ForgeGov source labels such as `[OPP-1]`, `[PIPE-1]`, and `[TASK-1]`
- A real assistant loading state and model status in the frontend

## Added: opportunity pages load data immediately

When a user opens Federal Contract Opportunities or Federal Grant Opportunities, ForgeGov now automatically requests the newest available live records. Users no longer see an empty page that requires an initial search click.

- SAM.gov defaults to the latest 30-day posting window already enforced by the backend integration.
- Grants.gov defaults to forecasted and posted opportunities.
- Initial results are sorted newest-first on the loaded page.
- Search and filter actions replace the recent-data view with matching results.
- Unsupported opportunity connectors remain explicit and do not display fabricated records.

## Environment behavior corrected

Changing `.env` does not update environment variables inside an already-created container. The installer and verifier now recreate containers with `--force-recreate` so `OPENAI_API_KEY` and other updated values are actually loaded.

## Validation

- Python source compilation
- Django system check and migration drift check
- Backend test suite, including OpenAI request mocking and cross-workspace context isolation
- Frontend lint and TypeScript checks
- Production Next.js image build
- Live SAM.gov verification
- Minimal live OpenAI Responses API verification when running `VERIFY.command`
