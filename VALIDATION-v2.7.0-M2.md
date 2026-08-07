# ForgeGov v2.7.0-M2 Validation

Source-level validation performed before packaging:
- Python compile and AST parsing.
- Migration/model field comparison.
- URL/import assertions.
- TypeScript/TSX syntax parsing.
- Package and API version alignment.
- Connector registry and reference-connector assertions.

Local Docker remains the final gate for Django migrations/tests, ESLint, TypeScript type checking, Next.js production build, live USAspending connectivity, and responsive browser validation.
