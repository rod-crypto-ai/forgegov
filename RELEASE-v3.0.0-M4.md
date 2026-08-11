# ForgeGov v3.0.0-M4 — Portfolio Revenue & Profit Intelligence

## Executive Portfolio
New Reports workspace:
- Reports → Executive Portfolio
- Active pipeline value
- Probability-weighted pipeline value
- Modeled revenue
- Modeled delivery cost
- Projected profit
- Weighted projected profit
- Portfolio margin
- Awarded backlog
- Option-year exposure
- Recommended working capital
- Working-capital gap
- Pricing coverage across active pursuits

## Portfolio calculations
The executive rollup uses the actual ForgeGov records already built in v3:
- Pipeline stages and probability of win
- Latest pricing revision per opportunity
- M1 cost/profit/margin
- M3 cash-flow and working-capital assumptions
- Awarded Proposal Closeout values for backlog
- CLIN option-year pricing for option exposure

Lost, No-Bid, and Archived pipeline items are excluded from active financial forecasts.

## Risk intelligence
Portfolio-level guardrails now detect:
- customer / agency concentration
- portfolio working-capital shortfall
- low modeled margin
- option-year dependency
- multiple High / Critical liquidity pursuits

## Executive snapshot history
Portfolio snapshots persist:
- pipeline value
- weighted pipeline
- modeled revenue
- profit
- backlog
- working-capital requirement/gap
- portfolio margin
- agency concentration
- liquidity risk summary

## API
- `GET /api/reports/portfolio-intelligence/`
- `POST /api/reports/portfolio-intelligence/` records an executive snapshot.

## Migration
- `0024_portfolio_revenue_profit_intelligence.py`

## v3.0 pricing/economics epic
- M1 Pricing & Economics Foundation
- M2 Price-to-Win Intelligence
- M3 Prime/Subcontractor + Cash-Flow Economics
- M4 Portfolio Revenue & Profit Intelligence
