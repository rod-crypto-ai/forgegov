# ForgeGov v2.9.0-M1 Validation Report

## Source validation completed
- Uploaded baseline verified as v2.8.0-m2.3.
- Latest migration verified as 0017.
- M2.3 health-test expectations were present in the uploaded baseline.
- Modified Python files compile successfully.
- New proposal-workspace route and frontend component are present.
- Backend/frontend versions aligned to 2.9.0-m1.
- No 0018 migration was added.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py check`
4. `python manage.py test core --verbosity 2`
5. `npm run lint`
6. `npx tsc --noEmit`
7. `npm run build`
8. Verify Proposal Workspace on desktop, iPad portrait/landscape, and phone.
9. Regression-test Command Center, Executive Capture, Win Strategy, document intelligence, USAspending, Live Web, Pipeline, Project Rooms, Network, and invitations.
