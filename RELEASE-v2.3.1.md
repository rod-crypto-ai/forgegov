# ForgeGov v2.3.1 Integration Patch

This patch makes the Phase 2 and Phase 3 features discoverable and visibly verifiable in production.

## Changes
- Adds a prominent dashboard release panel linking to Project Rooms and opportunity analysis.
- Adds Project Rooms to the dashboard workspace launcher.
- Keeps Project Rooms in the expanded Capture navigation group.
- Fixes navigation highlighting for nested routes such as `/project-rooms/<id>`.
- Adds a visible `LIVE BUILD v2.3.1` marker in the sidebar.
- Adds a `NEW` badge to the ForgeAI Briefing tab.
- Updates backend health version and health tests to `2.3.1`.
- Updates frontend package version to `2.3.1`.

## Production verification
After deployment, confirm:
1. Sidebar displays `LIVE BUILD v2.3.1`.
2. Dashboard displays the v2.3 release spotlight.
3. Project Rooms opens from the dashboard and Capture navigation.
4. A federal contract opportunity shows the ForgeAI Briefing tab with a NEW badge.
5. `/api/health/` reports version `2.3.1`.
