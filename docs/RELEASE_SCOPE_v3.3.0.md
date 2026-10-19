# ForgeGov v3.3.0 — Commercial Subscription & Launch Readiness

## Release objective

Make ForgeGov commercially operable without weakening tenant isolation, silently restricting
existing customers, or claiming that payment processing is active before Stripe has been
configured and verified in the target environment.

## Approved product direction

- Preserve the established ForgeGov product and release sequence.
- Position ForgeGov against a $2,000 annual value standard.
- Keep existing organizations and customer data accessible during the transition.
- Separate plan entitlements from metered usage.
- Keep billing administration limited to workspace owners and administrators.
- Preserve permanent, provider-independent grandfathered access for the existing Howard Dynamics and Strictly Hunter workspaces; they must never be offered Checkout or charged a subscription.
- Preserve current Django, PostgreSQL, Redis, session-cookie, Microsoft 365, and security architecture.
- Require a rollback reference before every production release.
- Use Stripe-hosted Checkout and Customer Portal pages; ForgeGov never receives card data.
- Publish one ForgeGov Professional offer at $2,000 per year with a 30-day trial.
- Measure usage for launch analysis without enforcing usage caps in v3.3.0.

## v3.3.0 scope

### Commercial foundation

- Provider-neutral subscription-plan catalog.
- One organization-scoped subscription record per workspace.
- Explicit trial, active, past-due, paused, cancelled, and expired states.
- Separate feature entitlements and usage limits.
- Time-windowed usage counters with atomic increment behavior.
- Idempotent, redacted billing-event records and a signed Stripe webhook adapter.
- Provider-state timestamps prevent older, out-of-order billing events from replacing newer subscription state.
- Existing workspaces migrated to protected legacy access; no current user is downgraded.

### Customer experience

- Workspace billing and access page.
- A clearly labeled grandfathered-access state with no payment or customer-portal actions.
- Clear plan, renewal/trial, payment-provider, entitlement, and usage presentation.
- Honest unavailable states when checkout or customer-portal access is not configured.
- Account/settings navigation available only to authorized billing administrators.

### Security and operations

- Tenant-scoped billing queries.
- Owner/admin authorization for billing data and actions.
- No card data stored by ForgeGov.
- No client-controlled price, plan entitlement, or subscription-state mutation.
- Audit records for subscription administration.
- Health/readiness details remain free of billing secrets and customer identifiers.

### Launch validation

- Subscription state-transition tests.
- Billing-role and cross-tenant isolation tests.
- Usage-counter concurrency and window tests.
- Existing-customer access regression tests.
- Signed Stripe webhook, replay, and tenant-mapping tests.
- Frontend responsive, keyboard, screen-reader, error, empty, and loading-state tests.
- Full release validation, dependency scans, secret scan, backup, and isolated restore.

## Remaining approval and configuration gates

The following remain configuration or approval gates, not assumptions:

- Stripe merchant-account activation, price-object creation, and production secrets.
- Tax treatment; whether payment details are required for the trial; and whether a no-payment-method trial cancels or pauses at expiration.
- Seat policy; v3.3.0 records the provider quantity but does not enforce a seat limit.
- Refund, cancellation, grace-period, and collections policy.
- Final Terms of Use and Privacy Policy language or legal approval.

Checkout fails closed unless the provider, enablement flag, Stripe price, API secret, webhook
secret, and trial payment-method policy are all present. The customer portal independently requires
its enablement flag, the Stripe provider, and API secret so an existing subscriber is not locked out
of payment management when new Checkout sessions are disabled. The UI must never claim automated
billing is operational when any required configuration is absent.

## Out of scope

- Marketplace purchasing.
- Multi-currency or usage-based invoicing.
- Government purchase orders and reseller workflows.
- New opportunity, capture, proposal, market-intelligence, or ForgeAI roadmap features.
- Replacing the existing identity or Microsoft 365 architecture.

## Production activation checklist

- Create and verify the annual recurring Stripe Price for exactly USD $2,000 and set its Price ID server-side.
- Configure the Stripe webhook endpoint at `/api/billing/stripe/webhook/` for Checkout completion, subscription create/update/delete, and paid/failed-invoice events.
- Store the Stripe API and webhook secrets only in the production secret manager.
- Explicitly select `required`, `optional_cancel`, or `optional_pause` for the trial payment-method policy.
- Approve and configure any past-due grace period; the safe default is zero days.
- Configure and test the Stripe Customer Portal cancellation and payment-method options.
- Complete test-mode Checkout, signed-webhook, replay, cancellation, payment-failure, recovery, and portal verification before enabling production billing.
