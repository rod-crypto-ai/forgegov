# ForgeGov v3.1.3 — Capture Intelligence & Competitive Positioning

## Purpose

Turn ForgeGov's existing opportunity, solicitation-document, USAspending award, pipeline, pricing, and company-profile evidence into a clearer capture decision layer without presenting inferred competitors, incumbents, or win themes as official facts.

## Added

- Opportunity competitive-positioning API: `/api/ai/opportunities/<source_id>/competitive-positioning/`
- Persistent `CompetitivePositionSnapshot` history for recorded capture reviews.
- Explainable qualification score with company fit, evidence coverage, proposal readiness, competitive position, agency-history coverage, and capture-execution factors.
- Agency buying-history rollups from stored federal award records: award volume, obligations, vendor concentration, repeat-vendor signal, common NAICS/PSC, top vendors, and recent awards.
- Competitor dossiers derived from official historical award evidence, including customer history, NAICS/PSC overlap, historical obligations, and explicit validation questions.
- Evidence-backed win-theme hypotheses with guardrails against invented customer priorities or unsupported differentiators.
- Black-hat research prompts that distinguish known historical signals from questions that still require validation.
- Capture Command Center panels for Qualification, Agency Buying History, Competitor Dossiers, and Win Themes.
- Competitor dossier links into the unified vendor profile.
- Vendor intelligence fallback that can build a profile directly from award history when a recipient has not yet been normalized into the Vendor table.
- Expanded unified vendor profiles with active-award count, agency reach, average award, PSC signals, top NAICS, and top awarding offices.

## Security / governance

- Competitive-position snapshots are organization-scoped.
- Viewer accounts can read capture intelligence but cannot record snapshots.
- Competitor and incumbent outputs retain explicit inference labels and bidder-intent warnings.
- No cross-company snapshot history is exposed.

## Database

Migration: `core.0031_capture_competitive_positioning`

## Release gate

`VERIFY_V3.1.3.command` runs a 20-stage local release gate and must pass before commit, push, or tag.
