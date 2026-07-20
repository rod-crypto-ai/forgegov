# Build Status — ForgeGov v0.2

## Verified

- ForgeGov naming and branding applied.
- Django migrations generated and applied in the test database.
- Five backend tests passed, including SAM.gov normalization, persistence, dashboard counts, API health, and opportunity search.
- Ruff backend lint passed.
- SAM.gov credentials remain outside source control.
- SAM.gov error handling does not return or log the API key in application-generated errors.
- Live-search throttling is configured to protect low daily API limits.

## Added in v0.2

- Expanded SAM.gov filters using the official v2 parameter names.
- Optional persistence of live results into the ForgeGov opportunity database.
- Normalized agency, subagency, office, NAICS, PSC, notice type, set-aside, deadlines, source links, and attachments metadata.
- Data-sync run history and a retryable Celery synchronization task.
- Real dashboard database metrics.
- Secure interactive local configuration script.

## Not verified in this environment

- A live SAM.gov request could not be completed because the build container could not resolve external DNS. This is an environment limitation, not proof that the supplied key works or fails.
- Docker execution is unavailable in this build environment.
- The npm package gateway timed out during dependency installation, so the Next.js lint/build still requires local or GitHub Actions verification.

The product is not production-ready yet. Authentication pages and organization-scoped authorization are the next mandatory milestone before public deployment.
