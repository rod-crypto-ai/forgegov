# ForgeGov v2.6.0 Validation

## Baseline confirmed
- Backend and frontend version 2.5.0 before changes.
- Migration 0013 present; no migration 0014.
- Final Unified Search correction present.
- Task model imported in Phase 5 tests.
- Final SAM and SUBNet assertions present.

## Source validation completed
- All backend Python files compile and parse.
- Modified TypeScript/TSX files parse successfully.
- CSS braces are balanced.
- Package and lockfile root versions are aligned to 2.6.0.
- Health endpoint and health tests are aligned to 2.6.0.
- No new database migration is required.

## Final local release gate required
The build environment cannot complete npm ci because its internal package mirror does not provide zod-validation-error@4.0.2. Before production release, run:
- python manage.py check
- python manage.py test core --verbosity 2
- npm run lint
- npm run typecheck
- npm run build
