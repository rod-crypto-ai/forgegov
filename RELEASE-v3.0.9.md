# ForgeGov v3.0.9 — Governance, Permissions & Enterprise Controls

## Release focus
ForgeGov v3.0.9 centralizes enterprise authorization rules and hardens cross-company collaboration.

## Included
- Runtime role/capability matrix for Owner, Admin, Capture, BD, Proposal, Pricing, Contributor, and Viewer.
- Time-bound Project Room partner access with explicit expiration and revocation state.
- Independent partner permissions for uploads, comments, pricing, sensitive documents, and exports.
- New Sensitive Document file classification alongside Internal, Shared, and Pricing Restricted.
- Project Room JSON exports filtered by the caller's effective authorization.
- Submission export role enforcement.
- Optional organization policy requiring recent authentication for exports and Project Room administration.
- Effective access returned by Project Room access APIs and visible in the UI.
- Cross-tenant regression coverage for Project Rooms and Platform Admin boundaries.
- Carries forward the v3.0.8 migration dependency and connector-test isolation corrections.

## Database
Migration: `core.0028_governance_permissions_enterprise_controls`.

## Release gate
Run `./VERIFY_V3.0.9.command` before commit, push, or tag.
