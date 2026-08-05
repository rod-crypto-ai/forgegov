# ForgeGov v2.7.0-M1.1 Validation

Validated in packaging environment:
- Python compile and AST parse
- TypeScript/TSX syntax parse for modified files
- Official Census 2022 NAICS catalog: 2,122 hierarchical records
- Migration/model alignment for NetworkConnection lifecycle
- SearXNG connector registration and JSON diagnostics
- Live USAspending incumbent fallback wiring
- Responsive CSS brace/source validation

Required locally before deployment:
- `python manage.py makemigrations --check`
- `python manage.py migrate`
- `python manage.py test core`
- `npm run lint`
- `npx tsc --noEmit`
- `npm run build`
- manual iPad portrait/landscape workflow test
