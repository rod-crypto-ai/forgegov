# ForgeGov v2.7.0 — Intelligence Foundation (Milestone 1)

## Delivered

- Modular intelligence package with source adapters, normalized schemas, services, and evidence helpers.
- Connector Manager API and responsive administration page.
- Normalized opportunity-intelligence API with:
  - official incumbent and historical-winner evidence from stored awards;
  - clearly labeled likely-competitor inference;
  - ForgeGov Network teaming recommendations;
  - source classification, confidence, timestamps, evidence, and warnings.
- Connector health for SAM.gov, USAspending, SBA SUBNet, and federal procurement forecasts.
- Version alignment to 2.7.0.
- No database migration required for this milestone.

## Trust rules

Official public data, ForgeGov platform data, user-contributed intelligence, and AI-derived inference remain visibly separate. Likely competitors are never represented as confirmed bidders.

## Local release gate

Run Django migration checks, backend tests, ESLint, TypeScript, Next.js production build, and manual responsive verification before deployment.
