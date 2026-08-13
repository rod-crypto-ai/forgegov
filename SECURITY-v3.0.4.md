# ForgeGov v3.0.4 Security Model

## Data classifications

### PUBLIC_GOVERNMENT
Examples:
- SAM.gov opportunity records
- USAspending award records
- public agency/vendor intelligence

These may be available to any authenticated ForgeGov company where the product intentionally exposes public-source intelligence.

### ORGANIZATION
Examples:
- pipeline
- capture notes
- internal opportunity documents
- AI conversations
- proposal state
- tasks
- saved searches

These are restricted to the owning ForgeGov organization.

### FINANCIAL_SENSITIVE
Examples:
- cost build-up
- indirect rates
- profit
- margin
- Price-to-Win dollar range
- subcontractor economics
- cash-flow/working-capital details
- Executive Portfolio financials

Default roles:
- Owner
- Administrator
- Pricing Manager

### PROJECT_ROOM_SHARED
Only content explicitly marked Shared can cross a company boundary through a Project Room.

### PROJECT_ROOM_PRICING
Project Room pricing files require a separate `can_view_pricing` partner grant. This grant does not provide access to the owner company's internal Pricing Workspace, Executive Portfolio, private AI history, or other pursuits.

## Authorization rule
Every sensitive request is evaluated as:

Authenticated user
→ active account
→ active organization
→ active Membership
→ current role/capability
→ object organization relationship
→ optional Project Room relationship
→ explicit visibility/grant
→ allow

Any failed step denies access.

## Important release rule
Frontend visibility is not authorization. API permissions and organization-scoped querysets remain authoritative.
