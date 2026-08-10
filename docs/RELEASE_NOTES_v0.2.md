# ForgeGov v0.2 Release Notes

This release turns the original interface scaffold into the first real government-data workflow.

1. Search SAM.gov from the ForgeGov backend without exposing credentials to the browser.
2. Filter by title, agency, NAICS, PSC, state, notice type, set-aside, solicitation number, and date ranges.
3. Persist returned opportunities into the ForgeGov database with idempotent update behavior.
4. Track synchronization results and failures.
5. Display database-backed dashboard counts.
6. Protect live search with configurable throttling.
7. Configure secrets through an interactive script rather than editing source code.

Next release target: account registration, workspace onboarding, invitations, organization-scoped permissions, and converting a stored opportunity into a pipeline pursuit.
