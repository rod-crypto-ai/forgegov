# ForgeGov v2.8.0-M1 — Document Intelligence Foundation

## Scope
- Builds on the verified v2.7.0-M3 baseline plus USAspending and Live Web fixes.
- Adds deterministic solicitation signal extraction before AI analysis.
- Adds ZIP attachment ingestion with safe member filtering and existing file-type parsers.
- Adds evidence-coverage capture readiness scoring.
- Adds one-click analyses for Sections L/M, CLINs & deliverables, and security/compliance.
- Adds a document-intelligence API endpoint.
- Enhances the Opportunity Briefing UI with readiness and extracted-signal cards.

## Truthfulness / limitations
- Scanned-image OCR is **not** claimed in this milestone because the baseline has no OCR runtime dependency.
- Capture readiness measures evidence coverage only; it is not a legal compliance opinion or win probability.
- Deterministic extraction is a candidate-finding layer. Users must verify requirements against cited source documents.
- No database migration is required; structured extraction is stored in the existing OpportunityDocument.metadata JSON field.

## New endpoint
GET /api/ai/opportunities/<source_id>/document-intelligence/

## Release gate
Run Django migration check, Django tests, ESLint, TypeScript, Next production build, and manual responsive validation before deployment.
