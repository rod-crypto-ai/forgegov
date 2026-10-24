# Isolated staging validation

Create a **new** Render Blueprint from `stabilization/v3.3.0-experience-audit`
using `render.staging.yaml`. Do not apply the production `render.yaml` or
associate staging with existing production services.

## Deployment boundary

- All seven resource names begin with `forgegov-staging`.
- Ohio separates staging's private network from production in Oregon.
- PostgreSQL and Key Value deny external connections and reference only new
  staging resources. Never restore a production backup or import customer data.
- Django and SearXNG secrets are generated independently. No production
  environment groups, credentials, domains, or datastore URLs are copied.
- Public registration, outgoing email, scheduled source syncs, digests, alerts,
  checkout, and the billing portal start disabled.
- Application autodeploys are disabled. Review future Blueprint syncs separately.
- Free web services sleep and have usage limits. The free database expires;
  this environment is disposable and is not a production recovery target.
- Review Render's quoted compute charges before deploying. Provider usage and
  hosting extras must be considered separately.

## Authentication transport

The frontend uses `/api` and a build-time `API_PROXY_TARGET` pointing at the
staging API's Render external URL. Next.js forwards these requests to Django.
This keeps browser cookies on the frontend origin with HTTPS and SameSite=Lax.
The proxy configuration accepts only an HTTPS origin with no credentials,
path, query, or fragment. Without the variable, existing deployments retain
their direct API transport. Changing the proxy target requires a frontend build.

## Credentials and access

Enter dedicated staging SAM.gov and OpenAI credentials through Render's secure
environment settings. Use only the connected Forge-gov Stripe sandbox's test
key and a new signed webhook endpoint for this staging API. Never use a live
Stripe key. The sandbox annual price is preselected, but billing stays disabled
until the test credentials and webhook secret are installed and verified.

The four `sync: false` secret fields are supplied at creation or configured
afterward; Blueprint resyncs must not overwrite them with blank literal values.
Create only synthetic test organizations and users using an authorized staging
administration path; do not open unrestricted registration to bootstrap access.
Do not output passwords, keys, webhook secrets, or reset tokens into logs.

## Evidence required before release

1. Confirm every resource's region, datastore references, deployed commit, and
   health. Verify `/api/health/` and `/api/ready/` through both API and proxy.
2. Verify sign-in, refresh, logout, CSRF rejection, and tenant isolation through
   the proxy. Check response cookies and cross-origin rejection.
3. Complete the existing full-stack persistence workflows with synthetic data:
   tasks, Project Rooms, proposal revisions, and pricing reloads.
4. Run a bounded USAspending import. Verify classifications and source timestamps
   in new records and preserve honest partial-run/freshness labels. Verify live
   SAM.gov search separately; fixture success is not provider-health evidence.
5. Generate and review ForgeAI answers against their cited source evidence.
   Record latency, unsupported claims, and unavailable-source behavior.
6. Enable staging-only Stripe checkout and portal after configuration. Verify
   completed checkout, the 30-day trial, signed webhook processing, duplicate
   delivery handling, cancellation, and payment-failure behavior. Use test
   clocks/cards only. Retest grandfathered exemptions using synthetic fixtures.
7. Review phone, tablet, desktop, and both themes against the final revision.
   Rerun CI and preserve screenshots. Obtain legal review of commercial notices.

Passing infrastructure deployment does not satisfy these release gates.
Production deployment remains a separate reviewed action.
