# ForgeGov v2.7.0-M3 validation

Source-level checks performed before packaging:
- Python compilation and AST validation.
- No new migration added; latest migration remains 0017.
- Version strings aligned to 2.7.0-m3.
- Opportunity Intelligence endpoint consumed by the SAM opportunity workspace.
- Mission Control consumes award freshness and connector health.
- Responsive CSS includes desktop, laptop/tablet, and mobile collapse rules.

Local Docker remains the final gate for Django tests, migration parity, ESLint, TypeScript, Next.js production build, and live data verification.
