# ForgeGov v3.3.7

Session renewal reliability

An expired access cookie could prevent the refresh endpoint from validating a still-valid refresh token. Overlapping refresh calls could also produce a late failure response that erased a different tab's newly issued cookies.

- Let the refresh endpoint validate its own refresh credential without first requiring an access token. Retain explicit CSRF enforcement, active-account checks, session expiry/revocation checks, and token rotation/blacklisting.
- Reject invalid refresh requests without clearing shared cookies, so stale responses cannot erase a successfully renewed session.
- Coalesce refresh calls within a tab and serialize them across tabs when Web Locks is supported. Tokens remain HttpOnly and are never passed between tabs.
- Retry an unauthorized original request once after refresh, including when a concurrent tab may already have renewed the cookie. The server still validates that retry.
- Cover expired access cookies, late stale-token responses, revoked sessions, CSRF enforcement, and real two-tab expiry recovery in Chromium, Firefox, and WebKit against the disposable Docker backend.

No schema, membership, subscription, token lifetime, or payment-provider changes are included. Rollback revision is af6d4bfe75722894f0ee74c716659326286f90d9 (v3.3.6).

Production OpenAI credentials were rejected during the preceding live checks and still require account-owner replacement or reauthorization. Complete scheduled ingestion coverage, reconciliation of historical stuck runs, delivered email, and payment completion remain separate acceptance gates.
