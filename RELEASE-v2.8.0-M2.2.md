# ForgeGov v2.8.0-M2.2 — Competition & Win Strategy

This milestone adds an evidence-backed Win Strategy workspace to every federal opportunity.

## Included
- Likely incumbent signal derived from similar official historical award records, with confidence and a verification warning.
- Similar-contract matching across agency, NAICS, PSC, and scope terms.
- Likely competitor ranking from historical awards, explicitly labeled as inference rather than an official bidder list.
- ForgeGov Network teaming recommendations using NAICS, PSC, certification/capability evidence, profile verification, and existing partnership status.
- Initial compliance matrix generated from indexed solicitation evidence (Section L/M, FAR/DFARS, certification/security, and deliverable signals).
- Pricing-readiness score based on whether the evidence needed to build a price exists; ForgeGov does not invent a bid price.
- Evidence-backed strengths, gaps, potential discriminators, and customer/evaluation hypotheses.
- Prioritized win-strategy actions.
- Dedicated responsive Win Strategy tab in the SAM.gov Opportunity Workspace.
- No database migration required; latest migration remains `0017_award_ingestion_connector_sdk`.

## Intelligence boundaries
- Incumbent is labeled **likely** until predecessor evidence is verified.
- Competitors are inferred from historical award overlap and are never represented as known bidders.
- Teaming recommendations are ForgeGov Network matches, not endorsements or availability guarantees.
- Pricing readiness measures evidence completeness, not price reasonableness or a proposed bid value.
- Customer priorities are hypotheses unless Section M, official Q&A, or other evidence supports them.
