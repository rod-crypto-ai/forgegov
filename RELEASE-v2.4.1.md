# ForgeGov v2.4.1 — Stability & UX Corrections

## Included
- Clean, decoded SAM.gov attachment names with reliable fallbacks.
- Select individual attachments before ingestion.
- ForgeAI opportunity analysis and Q&A work without ingested attachments.
- Clear context indicator: opportunity-only or opportunity + documents.
- More natural capture-manager AI response style and cleaner answer layout.
- Collapsible desktop sidebar with remembered preference.
- Removed the production build badge from navigation; version moved to Profile & Workspace.
- Working workspace dropdown with Profile, Team, and Settings destinations.
- Company Profile moved from Network into Profile & Workspace.
- Compact SBA SUBNet cards and corrected 20-record indexed pagination behavior.
- Version 2.4.1 across backend health checks and frontend package metadata.

## Validation performed
- Backend Python compilation and AST parsing.
- TypeScript parser validation for all modified TSX files.
- No schema/model changes; no new migration is required.
- Full local Docker lint, TypeScript, build, and Django test suites remain the release gate.
