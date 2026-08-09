# ForgeGov v2.9.0-M2 Validation Report

## Baseline
Built from the uploaded post-fix GitHub `main` ZIP.
- Baseline version: `2.9.0-m1`
- M1 health-test expectations present.
- M1 Awards-page hook fix retained.
- Latest baseline migration: `0017_award_ingestion_connector_sdk.py`

## Source-level validation completed
- Modified backend Python files pass AST parsing.
- Backend/frontend version aligned to `2.9.0-m2`.
- New Proposal Execution routes are registered in source.
- Migration `0018_proposal_execution_review_management.py` is included.
- New Proposal Execution tests were added.
- TSX delimiter balance checks passed for modified opportunity/proposal files.
- Existing USAspending and Live Web fixes remain in the baseline.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py showmigrations core`
4. `python manage.py check`
5. `python manage.py test core --verbosity 2`
6. `npm run lint`
7. `npx tsc --noEmit`
8. `npm run build`
9. Test requirement assignment/status persistence.
10. Test Pink/Red/Gold/Final review status persistence.
11. Test findings creation/resolution.
12. Test amendment-impact detection and baseline acknowledgement.
13. Test submission-readiness gate.
14. Regression-test M1 Proposal Workspace, Command Center, Win Strategy, Executive Capture, USAspending, Live Web, Pipeline, Project Rooms, Network, and invitations.

## Migration expectation
After migration, `showmigrations core` must include:
`[X] 0018_proposal_execution_review_management`
