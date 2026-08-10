# ForgeGov v0.3 — Navigation and Intelligence Expansion

This release replaces the thin starter interface with a deeper government-contracting workspace modeled around the functional breadth shown in the supplied references.

## Major changes

- Rebuilt the sidebar into expandable product groups.
- Added more than 30 routed module views.
- Rebuilt the dashboard around capture operations and real database totals.
- Added advanced SAM.gov opportunity search and operational result actions.
- Added API-backed explorer pages with table search, refresh, and CSV export.
- Added models and endpoints for awards, vendors, agencies, contacts, contact groups, pursuits, teaming, files, participants, and categories.
- Added ForgeGov AI and reporting workspaces with honest connector status.
- Fixed the duplicated dashboard markup that caused the earlier Next.js build error.

## Important limitation

The expanded navigation makes the product structure complete enough to continue development, but not every external source is live. SAM.gov contract opportunities are the only fully implemented public search integration in this release. Other modules expose working workspace routes and database APIs but still require ingestion connectors and complete forms.
