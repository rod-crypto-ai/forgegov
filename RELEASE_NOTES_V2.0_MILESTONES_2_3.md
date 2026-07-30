# ForgeGov v2.0 — Internal Milestones 2 and 3

## Milestone 2: Opportunity Workspace

- Persistent per-organization opportunity workspace
- Capture summary, working notes, risk register, and bid/no-bid decision
- Persistent compliance checklist with completion tracking
- Starter compliance checklist derived from live SAM.gov metadata
- Opportunity timeline for posted, modified, deadline, archive, and workspace activity
- Internal document viewer retained with official-source fallback
- Contextual AI retained and expanded with preset executive summary, requirements, risk, and bid/no-bid analyses
- Original SAM.gov document filenames retained
- Incumbent and competitor signals remain linked to company profiles

## Milestone 3: Capture and Teaming

- Pursuit dashboard with active value, weighted value, near-term deadlines, and stage counts
- Rich pursuit editor for stage, estimated value, probability of win, due date, incumbent, and next action
- Weighted pursuit value displayed at record level
- Persistent teaming activity history
- Teaming notes, emails, calls, meetings, and follow-up records
- Follow-up dates and completion tracking
- Partner point-of-contact field exposed in the teaming workspace
- Existing delete, archive/status, profile, and outreach actions retained

## Database

Migration `0008_opportunityworkspace_teamingactivity.py` adds:

- `OpportunityWorkspace`
- `TeamingActivity`

Run `python manage.py migrate` after installing the update.
