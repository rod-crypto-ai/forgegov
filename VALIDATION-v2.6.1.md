# ForgeGov v2.6.1 Validation

Source baseline: uploaded GitHub main archive dated 2026-08-03.

Completed here:
- Backend Python compilation and AST parsing
- TypeScript/TSX syntax parsing for every modified frontend file
- Version alignment checks
- Migration/source alignment review for migration 0014
- Route assertions for Company Hub, notification center, invitation actions, and Project Room invitation management
- Security review for active membership enforcement and read-only notification fields
- Archive-root verification

Final local release gate required:
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate`
- Full Django test suite
- ESLint
- TypeScript type check
- Next.js production build
- End-to-end invitation email and notification test with the configured production email backend
- Responsive testing at desktop, tablet, and mobile widths
