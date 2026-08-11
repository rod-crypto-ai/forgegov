# ForgeGov v3.0.0-M2 — Price-to-Win Intelligence

## Competitive pricing model
- Builds a competitive pricing range from stored official federal award history.
- Prioritizes comparables using agency, NAICS, PSC, jurisdiction, and award-type match strength.
- Uses stronger comparables when enough evidence exists and transparently broadens the evidence set when it does not.
- Normalizes historical award values with the opportunity pricing plan's annual escalation assumption when source dates support it.
- Generates:
  - Competitive Floor
  - Modeled Target
  - Protective Ceiling
- Calculates confidence from comparable quantity, match quality, recency, and whether a real ForgeGov cost model exists.
- Never represents the range as a competitor's confidential bid or factual prediction.

## Financial viability
Each modeled market price is tested against the M1 cost model:
- projected profit
- projected margin
- configured minimum margin
- economic viability
- target-bid market position

Positions:
- below competitive floor
- competitive
- above target but within range
- above modeled range

## Evidence
- Displays comparable recipient, award number, agency, NAICS, PSC, historical value, normalized value, match score, and official source URL when stored.
- Warnings explicitly identify sparse or weak evidence.
- Model assumptions are visible and separated from official facts.

## Persistence
- Price-to-win snapshots can be recorded for decision history.
- Snapshot stores modeled range, confidence, evidence count, comparable award IDs, assumptions, warnings, and pricing revision.

## Pursuit Decision integration
Pursuit Decision Intelligence now receives:
- PTW floor
- PTW target
- PTW ceiling
- PTW confidence
- current bid position
- whether the modeled target clears the configured margin floor
- PTW evidence classification

A pursuit receives an explicit condition when the modeled competitive target requires an unacceptable margin or PTW evidence is too weak.

## API
- `GET /api/pricing/opportunities/<source_id>/price-to-win/`
- `POST /api/pricing/opportunities/<source_id>/price-to-win/` records a snapshot.

## Migration
- `0022_price_to_win_intelligence.py`

## Next
- v3.0-M3 Prime/Subcontractor + Cash-Flow Economics
- v3.0-M4 Portfolio Revenue & Profit Intelligence
