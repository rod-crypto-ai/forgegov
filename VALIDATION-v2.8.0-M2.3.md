# ForgeGov v2.8.0-M2.3 Validation Report

## Source-level validation completed
- Modified backend Python files compile.
- Python AST parsing passed for views, URLs, tests, and Capture Command Center service.
- Package JSON files parse successfully.
- Backend/frontend version aligned to `2.8.0-m2.3`.
- New Command Center route exists.
- New Command Center tests added.
- No `0018` migration exists.
- TypeScript parser reached only missing dependency/module errors because node_modules is not present in the packaging environment; no TSX parse/syntax errors were found.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py check`
4. `python manage.py test core --verbosity 2`
5. `npm run lint`
6. `npx tsc --noEmit`
7. `npm run build`
8. Verify Command Center on desktop, iPad portrait/landscape, and phone.
9. Regression-test Executive Capture, Win Strategy, USAspending, Live Web, Pipeline, Project Rooms, Network, and invitations.

## Known scope boundary
This milestone provides an operational Capture Command Center using existing ForgeGov records. Native PDF/PPTX executive export generation is not claimed in M2.3.
