# ForgeGov v3.3.3 — Product-led public experience

## Scope
Replace the public marketing page with a server-rendered, product-led landing page. Preserve the approved logo and navy/blue/silver identity. Add clear annual pricing, runtime-aware account creation, and a separate persisted inquiry path. This follows the existing commercial-readiness roadmap; it does not activate payments or change subscription exemptions.

## Product evidence
Five images in `frontend/public/product/` were captured from the actual authenticated Next.js application backed by a disposable Django/SQLite database, with no browser API fixtures. The workspace, opportunity, agency, award, and partner names and values are deliberate demonstration records. Every published screenshot is labeled as demonstration data, not live government listings or customer evidence. No customer account, private production workspace, or live AI answer is published.

- Discovery: real filters, synchronized records, official-source links, and honest `Not Run` sync status.
- Qualification: actual agency-pattern analysis over stored sample awards.
- Capture: actual stages, calculated portfolio metrics, next actions, and stage-gate findings.
- Project Rooms: actual People & access controls for two demonstration partner companies, including pricing, sensitive files, export, and expiration.
- ForgeAI: actual research workspace and provider-status controls. The demonstration has no model credentials, and no fabricated generated answer is shown.

Reproduce using a disposable database and approved test identities. Never capture customer or payment information for public assets. Local capture scripts restrict authenticated browser requests to loopback hosts.

## Conversion and access
Live read-only registration-config inspection returned `public_registration=true`. Calls to action read the same endpoint at runtime: public mode links to `/register`; controlled mode links to `/request-access`. Server-rendered fallback links to registration, which still enforces the backend's current policy. Pricing is the existing Professional offering: $2,000 USD/year. No added tiers, seat limits, win-rate statistics, certifications, endorsements, or paid-checkout promises.

New `/request-access` and `/support` forms POST to a CSRF-protected, anonymous, IP-throttled inquiry endpoint (5/hour). Validated inputs require privacy acknowledgment and pass a honeypot. The API only returns a random reference and status. It never creates accounts, memberships, subscriptions, invitations, or email messages. Staff with the explicit Django `PublicInquiry` model permission can review inquiries in Django administration. Review is manual, without a promised response time. Privacy copy describes the newly stored contact fields.

## Shared experience and SEO
Scoped public typography/spacing and responsive controls; accessible keyboard tabs and a native modal for full-size screenshots; public support and legal navigation. The homepage content and metadata render before authentication resolves. Dashboard code loads separately for authenticated users. Canonical, Open Graph, Twitter, robots, and sitemap entries added. Images are WebP, responsive, and sized to reserve layout space.

Source audit found and corrected actual app defects: room summary cards now size to their container, partner-permission company names receive their own full-width row, and capture-review empty states retain vertical text flow.

## Validation and rollout
Run backend tests, migration consistency, source/security checks, frontend lint/typecheck/build/audit, existing responsive suites, new 18-case public suite, and isolated full-stack E2E. Public suite checks SSR, six widths in three engines, tabs and keyboard, enlarged-image modal, CTAs, controlled registration, forms, legal/support pages, and overflow. Full-stack E2E adds real public-inquiry persistence and retains task, room, proposal, and pricing checks. Compare public before/after screenshots at 390, 768, and 1440px.

Do not merge until candidate checks pass. Preserve commit `8e127571b2c3aa2d2b578aeedb899afb9154e644` as `rollback/pre-v3.3.3`; main CI creates annotated release/rollback tags after checks pass. Verify Render rollout and public HTTP/browser smoke checks after merge.

## Rollback compatibility
Migration 0043 only adds a new inquiry table. Existing models and data are unchanged. v3.3.2 continues to operate with the extra table present; do not reverse/drop the table during an application rollback. Retain inquiry records for review. Revert application services to the retained v3.3.2 artifact/commit if a critical smoke check fails, then verify readiness and public sign-in. The existing Docker backup/restore gate validates an isolated restore.

## Remaining commercial gates
Legal pages remain operational drafts awaiting qualified legal approval. This release does not certify legal, tax, security accreditation, or full commercial billing readiness. Stripe sandbox E2E, live-payment activation, and live-provider quality gates remain separate. Production customer credentials, integrations, tenant permissions, and Howard Dynamics/Strictly Hunter permanent no-fee access are unchanged.

## Competitive claim check (2026-10-25)
GovDash describes capture collaboration and teaming partners; GovTribe describes teaming requests and capture workflows. Consequently, no exclusivity or superiority claim is published. ForgeGov's page demonstrates its own connected workflow instead.
Primary references: https://www.govdash.com/capture ; https://support.govdash.com/docs/managing-teaming-partners ; https://govtribe.com/docs/govtribe-user-guide/teaming/
