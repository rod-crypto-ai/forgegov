# ForgeGov v2.2.0 — ForgeAI Document Intelligence

## Added
- Secure, organization-scoped solicitation document ingestion.
- PDF, DOCX, XLSX, TXT, and HTML text extraction.
- Chunked document indexing with filename, page, and worksheet citations.
- SSRF protection and a 25 MB source-file limit.
- Opportunity Briefing tab on SAM.gov opportunity pages.
- Cached executive briefings, requirements extraction, risk assessments, bid/no-bid briefs, compliance matrices, and amendment comparisons.
- Document-grounded question answering with visible source citations.
- Re-indexing and analysis refresh controls.
- Migration `0010_opportunity_document_intelligence`.

## Deployment
1. Rebuild backend and frontend containers.
2. Run `python manage.py migrate`.
3. Confirm `0010_opportunity_document_intelligence` is applied.
4. Open an opportunity, select **ForgeAI Briefing**, and ingest its public documents.

## Security
- Every document, passage, and analysis is scoped to the active organization.
- Project Room fields are included for the next shared-room permissions increment.
- Private, loopback, link-local, reserved, and multicast source URLs are rejected.
- AI receives only authorized extracted passages selected for the active opportunity.

## Validation note
Python source passed compile and AST checks. The frontend production build could not be executed in the artifact environment because its internal npm mirror does not contain `zod-validation-error@4.0.2`; run the normal Docker/GitHub build before production deployment.
