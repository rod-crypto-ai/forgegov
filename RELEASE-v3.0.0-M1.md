# ForgeGov v3.0.0-M1 — Pricing & Economics Foundation

## Pricing Workspace
- Persistent opportunity pricing plans with revision history.
- Draft, review, approved, and locked pricing states.
- Labor, materials, travel, equipment, subcontractor, bond, insurance, and other direct costs.
- Labor hours and rates remain distinct from quantity/unit-cost items.
- Opportunity-specific payroll burden, fringe, overhead, G&A, material handling, and subcontract handling rates.
- Annual/option-year escalation support.
- CLIN and option-year assignment.
- Competitive, Target, and Protective scenarios.
- Correct distinction between markup and margin.
- Pursuit-cost tracking.
- Economic guardrails for margin floor and subcontract concentration.
- Organization-level pricing-default API.
- Locked revisions can be cloned into a new editable revision.

## Opportunity integration
- New Pricing workspace positioned after Compliance and before Proposal.
- Existing Overview-first / ForgeGov-AI-second navigation remains intact.

## Pursuit Decision integration
Pursuit Decision Intelligence now consumes the actual ForgeGov pricing model when available:
- target bid price
- delivery cost
- projected profit
- projected margin
- pursuit cost
- subcontractor cost share
- pricing revision/status
- evidence that a real financial model exists

This replaces the old placeholder pricing economics when a pricing model has been built.

## API
- `GET/PATCH/POST /api/pricing/opportunities/<source_id>/`
- `GET/PATCH /api/pricing/profile/`

## Migration
- `0021_pricing_engine.py`

## Next v3 milestones
- M2 Price-to-Win Intelligence
- M3 Prime/Sub + Cash-Flow Economics
- M4 Portfolio Revenue & Profit Intelligence
