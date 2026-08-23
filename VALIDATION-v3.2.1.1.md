# ForgeGov v3.2.1.1 Validation

Run from the repository root:

```bash
./VERIFY_V3.2.1.1.command
```

The release is not approved for commit/tag until all 24 stages complete.

## New v3.2.1.1 regression focus

The dedicated `core.test_v3211_integrations_ux` suite verifies:
- Microsoft OAuth authorization uses PKCE and does not expose the client secret;
- Microsoft status is user scoped and never returns stored access/refresh tokens;
- revoked workspace access produces a clean authorization failure instead of a Microsoft Settings server error;
- Viewer roles cannot send external Microsoft actions;
- Microsoft callback returns safely to the ForgeGov Settings Center;
- detailed SUBNet workspaces include source, contact, prime award, parent-contract, and capture context;
- Pipeline/capture state does not cross company boundaries;
- non-SUBNet records cannot be opened through the subcontract-detail route.

## Manual responsive acceptance

After the automated frontend build passes, inspect the major authenticated pages at:
- 390px phone;
- 768px tablet;
- 1024px small laptop/tablet landscape;
- 1280px laptop;
- 1440px desktop;
- 1920px large desktop;
- 125% browser zoom;
- 150% browser zoom.

At each width, verify navigation, page headings, filters, action groups, tab rails, cards, data tables, Settings, federal opportunity detail, subcontract opportunity detail, Pipeline, Project Rooms, and Proposal Workspace. No primary action or source text should overlap or be clipped.

Success target:

```text
[24/24] Health + readiness + container status
ForgeGov v3.2.1.1 validation completed successfully.
```
