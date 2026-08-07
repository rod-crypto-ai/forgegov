# ForgeGov v2.8.0-M1 Validation Report

## Baseline
Built from the uploaded `forgegov-main 5.zip` project baseline.

## Included source-level fixes retained
- USAspending health probe uses `/api/v2/awards/last_updated/`.
- Live Web UI uses backend `web_search_status` instead of a generic reconnecting label.

## Document Intelligence Foundation
- Existing PDF, DOCX, XLSX/XLSM, HTML, and text extraction retained.
- ZIP attachment ingestion added with member-count, type, and file-size controls.
- Deterministic extraction added for Section L, Section M, CLIN/SUBCLIN/ELIN identifiers, FAR/DFARS references, key date candidates, CMMC/NIST/ISO signals, deliverable candidates, and labor-category/staffing candidates.
- Extracted signals are stored in existing `OpportunityDocument.metadata`; no schema migration is required.
- Capture-readiness evidence coverage score added.
- New analyses: Sections L & M, CLINs & deliverables, Security & compliance.
- New endpoint: `GET /api/ai/opportunities/<source_id>/document-intelligence/`.
- Opportunity Briefing UI now shows document readiness and extracted signal counts.

## Important limitation
Scanned-image OCR is not claimed in this milestone. The uploaded baseline does not include an OCR engine/runtime dependency. Image-only PDF pages may produce no readable text and will be reported as such rather than fabricated.

## Static validation completed
- Modified Python files compile successfully.
- Python AST parsing passed.
- JSON package manifests parse successfully.
- `package.json` and root `package-lock.json` are aligned to `2.8.0-m1`.
- Repaired the stale `ts-api-utils` lockfile version entry to its resolved package version (`2.5.0`).
- No `0018` migration exists or is required.
- USAspending health endpoint assertion passed.
- Live Web generic reconnecting-label regression assertions passed.
- TypeScript parsing reached only expected missing-module errors in this packaging environment; no TSX syntax/parsing errors were detected.

## Local release gate still required
Run in Docker before deployment:
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py migrate`
3. `python manage.py check`
4. `python manage.py test core --verbosity 2`
5. `npm run lint`
6. `npx tsc --noEmit`
7. `npm run build`
8. Manual document-ingestion and responsive testing.
