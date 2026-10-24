# ForgeGov 3.3.2 — Stable status marker geometry

Final v3.3.1 production screenshot review found desktop status indicators collapsing
to zero width while the surrounding header text retained its intrinsic width.
The shared source-health badge now preserves its width and its 9px status dot.
This applies to billing, Project Rooms, and subcontracting source status.

The existing cross-browser experience suite now measures the billing status dot
in both density modes and both themes at all five viewport sizes. All v3.3.1
layout, control, typography and workflow corrections remain included.

No API behavior, database schema, credentials, payment activation, permissions or
customer data changes are introduced. Existing workspaces remain exempt.
Rollback reference: `rollback/pre-v3.3.2`, preserving v3.3.1 production revision
`9a6f506c3b456213e9c60900a3b560d96e1f1c5b`. The earlier pre-v3.3.1 reference also
preserves the original production baseline.
