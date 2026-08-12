# ForgeGov v3.0.2 Validation Gate

Required local Docker validation:

1. `python manage.py makemigrations --check --dry-run`
2. `python manage.py migrate`
3. Confirm `core.0025_identity_account_foundation` is applied.
4. Confirm django-axes migrations apply.
5. `python manage.py check`
6. `python manage.py test core.tests.IdentityFoundationTests --verbosity 2`
7. Run invitation/security regression tests.
8. Run full `python manage.py test core`.
9. Frontend `npm run lint`.
10. Frontend `npx tsc --noEmit`.
11. Frontend `npm run build`.
12. Test private-beta registration without invitation → blocked.
13. Test invited registration → enters correct company.
14. Test public mode in local environment → verification email required.
15. Test existing company domain → no duplicate organization.
16. Verify company join request appears only after email verification.
17. Test password reset and token replay rejection.
18. Verify disabled/suspended account cannot use API after account state changes.
19. Verify suspended/cancelled organization cannot be switched into.
20. Verify `/account` security summary.
21. Verify Terms/Privacy acceptance is persisted with versions.
22. Confirm no secrets or raw verification/reset tokens appear in database/audit logs.
