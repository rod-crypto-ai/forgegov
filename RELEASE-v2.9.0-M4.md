# ForgeGov v2.9.0-M4 — Pursuit Decision Intelligence

- No new opportunity tab.
- Command Center now surfaces PURSUE / PURSUE WITH CONDITIONS / HOLD / NO-BID.
- Executive Capture now includes an explainable weighted scorecard, confidence, evidence coverage, bid economics, conditions, evidence classification, and persistent decision history.
- Probability of win is explicitly labeled decision-support inference, not fact.
- M3 closeout/debrief lessons are exposed as a learning feedback input.
- Migration: `0020_pursuit_decision_intelligence.py`.
- API: `GET/POST /api/ai/opportunities/<source_id>/pursuit-decision/`.
