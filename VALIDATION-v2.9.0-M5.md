# ForgeGov v2.9.0-M5 Validation

## Source validation completed
- Modified Python modules pass AST parsing.
- Frontend/backend version references aligned to `2.9.0-m5`.
- Old 8,000-character rejection removed.
- Opportunity contextual AI routes through `/ai/opportunities/<id>/ask/`.
- Compact source disclosures are present for federal contract and grant contextual AI.
- Assistant input limit updated to 50,000 characters.

## Local Docker release gate required
1. `python manage.py makemigrations --check --dry-run --verbosity 2`
2. `python manage.py check`
3. `python manage.py test core --verbosity 2`
4. `npm run lint`
5. `npx tsc --noEmit`
6. `npm run build`
7. Open a real SAM opportunity with HTML description and verify clean text.
8. Ask opportunity AI for an executive summary and verify structured sections.
9. Verify public attachments auto-index and document-supported answers cite them.
10. Verify POC/location/deadline appear when present in official data.
11. Verify Sources stays collapsed by default.
12. Regression-test M1-M4 proposal/capture/submission/pursuit workflows.
