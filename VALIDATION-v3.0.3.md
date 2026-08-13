# ForgeGov v3.0.3 Validation Gate

Required on the tested local Docker environment:

1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. Confirm `core.0026_mfa_sessions_passkeys` is `[X]`.
4. `python manage.py check`
5. `python manage.py test core.tests.MFAAndSessionSecurityTests --verbosity 2`
6. `python manage.py test core.tests.IdentityFoundationTests --verbosity 2`
7. Run InvitationSecurityTests + WorkspacePermissionTests.
8. Run the full `core` test suite.
9. Frontend `npm run lint`.
10. Frontend `npx tsc --noEmit`.
11. Frontend `npm run build`.
12. Enroll TOTP and verify 10 recovery codes are shown once.
13. Sign out and verify password login now requires MFA.
14. Use one recovery code and verify it cannot be reused.
15. Perform a passkey registration using Touch ID/Face ID/Windows Hello/security key.
16. Verify password + passkey MFA login works.
17. Verify Security Center lists the current browser session.
18. Revoke another session and confirm it loses API access.
19. Revoke the current session and confirm ForgeGov returns to sign-in.
20. Verify sensitive security actions are blocked until step-up succeeds.
21. Enable company-wide MFA only after all existing members enroll.
22. Invite a new user into an MFA-required company and confirm MFA enrollment occurs before workspace access.
23. Confirm production WebAuthn origin/RP settings use the actual ForgeGov domain, not localhost.
