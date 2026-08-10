# ForgeGov v2.9.0-M5 — AI Response & Document Intelligence Hardening

## Fixed
- Opportunity contextual AI now uses the opportunity-specific document intelligence endpoint instead of sending a hand-built blob to generic chat.
- Public SAM descriptions are converted from HTML to readable plain text and persisted.
- Opportunity AI automatically indexes available SAM attachments when document evidence has not been indexed yet.
- Document context now guarantees broad coverage across every indexed attachment before filling the remaining context budget with relevance-ranked passages.
- Opportunity context now surfaces structured fields including:
  - Agency / Office
  - Solicitation
  - Notice Type
  - Description / Scope
  - Place of Performance
  - Response Deadline
  - POC when available
  - NAICS / PSC
  - Set-Aside
- Opportunity answers now prefer clear GovCon headings instead of long unstructured prose.
- ForgeGov no longer claims the whole solicitation is missing when only a specific fact is absent.
- Generic chat input ceiling increased from 8,000 to 50,000 characters.
- OpenAI Responses API output extraction supports additional response shapes and retries once when a successful API response contains no text.
- Opportunity-specific AI provides a structured evidence fallback instead of a dead-end "no usable text output" message.
- Live web queries receive focused opportunity title / solicitation / agency / question metadata when live web is available.
- "Sources used" blocks are now compact collapsed disclosures and no longer consume large workspace areas.
- Generic AI grounding strips raw HTML from stored opportunity descriptions.

## Regression tests added
- HTML description cleanup.
- Inputs above the former 8,000-character ceiling.
- Structured opportunity context with POC.
- Cross-document context coverage.

## Version
`2.9.0-m5`

## Migration
None.
