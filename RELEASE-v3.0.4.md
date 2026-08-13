# ForgeGov v3.0.4 — Organization Access Control & Multi-Tenant Security Hardening

## Purpose
v3.0.4 hardens ForgeGov's authorization boundary before private beta. The release assumes public government opportunity/award data may be shared globally, while company-created workspace content remains tenant-owned unless explicitly shared through a Project Room.

## Tenant isolation
- Sensitive company data is resolved from the user's current active organization membership on every request.
- Knowing an object ID or public opportunity source ID is never sufficient to retrieve another organization's private state.
- Membership removal and role changes take effect on the next request; a new login is not required.
- Existing account and organization suspension controls from v3.0.3 remain enforced by authentication.

## Financial Sensitive access
The following roles can read/write detailed pricing and financial data:
- Owner
- Administrator
- Pricing Manager

Protected surfaces include:
- Pricing Workspace
- Cost Build-Up / CLINs / Indirect Rates
- Price-to-Win ranges
- Prime/Sub economics
- Cash-flow economics
- Executive Portfolio

Proposal/Capture users continue to receive pursuit decision support, but detailed cost, profit, margin, cash position, and PTW dollar values are redacted unless the user also holds Financial Sensitive access.

## Proposal / submission access
Proposal read:
- Owner
- Administrator
- Capture Manager
- Business Development
- Proposal Manager
- Contributor
- Viewer

Proposal write:
- Owner
- Administrator
- Capture Manager
- Proposal Manager
- Contributor

Submission mutation:
- Owner
- Administrator
- Proposal Manager

## Project Room trust boundary
- Owner-company users must be explicitly assigned to a Project Room unless they are company Owner/Admin recovery administrators.
- Partner-company access is granted only through a ProjectRoomPartner record.
- Shared records are visible to authorized partners.
- Internal records remain owner-company only.
- Pricing-classified Project Room files require an explicit partner `can_view_pricing` grant.
- Partner upload/comment permissions are enforced independently.
- Viewer-style partner access cannot mutate collaborative content.
- Only company Owner/Admin roles can manage room membership, partner companies, invitations, archive, or deletion.
- Project Room creators are automatically enrolled as room managers.

## User experience
`/auth/me/` now returns server-derived capabilities. The frontend uses those capabilities to:
- hide Pricing from users without Financial Sensitive access;
- hide Proposal/Reviews/Submission from users without proposal access;
- hide Executive Portfolio navigation from users without executive financial access.

The API remains the source of truth; hidden navigation is convenience, not the security boundary.

## Denied-access auditing
Denied sensitive operations generate `security.access_denied` AuditLog records with:
- actor
- current organization
- capability
- denial reason
- HTTP method
- request path
- IP address

Target-tenant details are intentionally not included in denial metadata.

## Hostile security regression suite
`MultiTenantSecurityHardeningTests` creates:
- Alpha Defense
- Bravo Federal
- Charlie Systems

and validates:
- cross-company pricing isolation;
- proposal isolation;
- AI conversation isolation;
- document intelligence isolation;
- Executive Portfolio role restrictions;
- Project Room ID guessing returns not found;
- internal and pricing Project Room files remain hidden from partners without an explicit grant;
- pricing sharing requires explicit partner authorization;
- non-admin users cannot escalate Project Room partner access;
- role changes take effect without a new login;
- membership removal takes effect without a new login;
- opportunity Overview redacts financial values for non-financial roles.

## Database
No new ForgeGov migration is required for v3.0.4. This milestone hardens authorization using the existing v3.0.3 schema.
