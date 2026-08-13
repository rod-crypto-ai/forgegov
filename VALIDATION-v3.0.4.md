# ForgeGov v3.0.4 Validation Gate

Required local Docker validation:

1. `python manage.py makemigrations --check --dry-run` → No changes detected.
2. `python manage.py check`.
3. `python manage.py test core.tests.MultiTenantSecurityHardeningTests --verbosity 2`.
4. Re-run v3.0.2 IdentityFoundationTests.
5. Re-run v3.0.3 MFAAndSessionSecurityTests.
6. Run WorkspacePermissionTests and InvitationSecurityTests.
7. Run full `python manage.py test core`.
8. Frontend `npm run lint`.
9. Frontend `npx tsc --noEmit`.
10. Frontend `npm run build`.
11. Alpha user manually requests Bravo-owned Project Room ID → 404.
12. Alpha Viewer opens Pricing URL manually → 403.
13. Alpha Proposal user opens Pricing URL manually → 403.
14. Pricing Manager opens Pricing → allowed.
15. Proposal Manager opens Proposal/Reviews → allowed.
16. Viewer cannot mutate proposal.
17. Partner room shows Shared file but not Internal file.
18. Pricing partner grant exposes only Project Room pricing files, not owner Pricing Workspace.
19. Remove a member while their browser is open; next protected request must fail.
20. Downgrade Pricing Manager to Viewer while browser remains open; next Pricing request must fail.
21. Confirm `security.access_denied` events appear in audit logs without foreign-tenant details.
22. Verify Executive Portfolio navigation is absent for non-financial roles and API still returns 403 if URL is entered manually.
