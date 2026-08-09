# ForgeGov v2.9.0-M3 Validation Report

## Baseline
Built from the uploaded `forgegov-main 10.zip` baseline.
- Baseline version verified as `2.9.0-m2`.
- Migration `0018_proposal_execution_review_management.py` verified present.
- `OpportunityWorkspace` test-import fix verified present.

## Source-level validation completed
- Modified backend Python files pass AST parsing.
- Backend/frontend version aligned to `2.9.0-m3`.
- Submission Control and export routes are registered in source.
- Migration `0019_submission_control_closeout.py` is included.
- Explicit database index names introduced by M3 are below Django's 30-character portability limit.
- New Submission Control backend tests were added.
- Modified TSX files passed TypeScript syntax parsing; the packaging environment lacks project node_modules, so only missing-module errors were observed during isolated checking.
- No full Django, ESLint, TypeScript project, or Next production build is claimed from the packaging environment.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py showmigrations core`
4. `python manage.py check`
5. `python manage.py test core --verbosity 2`
6. `npm run lint`
7. `npx tsc --noEmit`
8. `npm run build`
9. Verify `[X] 0019_submission_control_closeout`.
10. Verify submission is blocked until human gates are satisfied.
11. Verify final submission snapshot creation and persistence.
12. Verify PDF/XLSX/PPTX downloads.
13. Verify closeout/debrief/lessons-learned persistence.
14. Regression-test Proposal Execution, Proposal Workspace, Command Center, Win Strategy, Executive Capture, USAspending, Live Web, Pipeline, Project Rooms, Network, and invitations.
