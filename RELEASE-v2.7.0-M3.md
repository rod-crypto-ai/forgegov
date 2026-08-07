# ForgeGov v2.7.0-M3 — Mission Control + Opportunity Intelligence Workspace

## Mission Control
- Adds award freshness, connector health, recent award activity, and probability-weighted pipeline signals to the command center.
- Keeps operational actions, deadlines, collaboration, and market intelligence in one landing page.

## Opportunity Intelligence Workspace
- Adds a dedicated Intelligence tab to SAM.gov opportunity workspaces.
- Displays likely incumbent, past winners, likely competitors, teaming matches, and the evidence used to produce each signal.
- Keeps official public data, ForgeGov platform data, and AI-derived inference visibly separated.
- Adds explicit refresh and unavailable-data states instead of blank intelligence panels.

## Data integrity
- Uses the v2.7.0-M2 normalized award store and existing live USAspending fallback.
- Does not represent inferred competitors as official bidders.
- No new database migration is required.
