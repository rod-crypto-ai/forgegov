# ForgeGov v3.0.0-M3 — Prime/Subcontractor + Cash-Flow Economics

## Prime / Subcontractor Economics
- Persistent subcontractor economic models tied to the active pricing revision.
- Captures:
  - quoted subcontract cost
  - prime markup
  - management burden
  - insurance cost
  - contingency
  - deposit requirement
  - subcontractor payment terms
  - monthly burn
  - quote/source reference
- Calculates:
  - prime revenue
  - net prime contribution
  - effective contribution margin
  - required subcontractor deposit
- Makes low-margin prime/sub structures visible before bid authorization.

## Cash-Flow & Working-Capital Model
- Opportunity-specific performance period.
- Government payment-lag assumption.
- Mobilization cost.
- Available working capital.
- Delivery burn rate.
- Payment-lag exposure.
- Subcontractor deposit exposure.
- Subcontractor timing mismatch exposure.
- Recommended working capital.
- Working-capital gap.
- Capital coverage percentage.
- Liquidity risk rating:
  - Low
  - Moderate
  - High
  - Critical
- Explicit warnings when a profitable contract may still create liquidity pressure.

## Revision Control
- Pricing revisions carry forward:
  - payment timing
  - performance duration
  - mobilization assumptions
  - available working capital
  - subcontractor models
- Locked pricing revisions remain immutable.

## Pursuit Decision Integration
Pursuit Decision Intelligence now consumes:
- prime/sub effective contribution margin
- recommended working capital
- available working capital
- working-capital gap
- working-capital risk
- prime/sub evidence status
- cash-flow evidence status

ForgeGov adds decision conditions when:
- working-capital risk is High or Critical
- prime/sub contribution margin is below 5%

## Pricing Workspace
New M3 sections:
- Prime / Sub
- Cash Flow

These live inside the existing Pricing workspace rather than adding more opportunity-level tabs.

## API
- `GET/PATCH/POST /api/pricing/opportunities/<source_id>/prime-sub-cashflow/`

## Migration
- `0023_prime_sub_cashflow_economics.py`

## Next
- v3.0-M4 Portfolio Revenue & Profit Intelligence
