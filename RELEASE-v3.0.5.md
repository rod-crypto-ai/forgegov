# ForgeGov v3.0.5 — Platform Administration & Private Beta Control Plane

## Mission

Provide a separate ForgeGov operator control plane without weakening organization tenancy or converting tenant administrators into platform administrators.

## Delivered scope

1. Command Dashboard
2. Organization Administration
3. User Administration
4. Private Beta Access
5. Security Operations
6. Feature Controls
7. System Operations

## Authority model

- Platform Super Admin: privileged mutations.
- Platform Support Admin: read/operational visibility only.
- Tenant roles never imply platform authority.
- A non-superuser PlatformAdminGrant must be active and explicitly MFA-verified before it authorizes the platform control plane.

## Organization lifecycle

pending → approved → active

Administrative exception states:
rejected, suspended, disabled

## User lifecycle

invited → active → suspended / disabled

## Private beta

pending → approve / reject / request information

Approval records reviewer and timestamp. Organization approval enables beta access.

## Feature controls

ForgeAI, Pricing, Proposal tools, Project Rooms, Executive Portfolio, Advanced Award Intelligence,
Grants, SUBNet, Awards, Forecasts, Contract Vehicles, Network, and Experimental features.

Feature-state API is platform-admin protected. Product-module backend enforcement must be wired by the owning feature
before relying on a flag as an authorization boundary; the control-plane flag itself is not represented as a substitute for
tenant authorization.

## System operations

Reuses the existing ForgeGov connector registry/health services when available.

## Maintenance mode

NORMAL / MAINTENANCE platform state. Maintenance blocks ordinary authenticated product traffic while preserving health/auth
and platform administration.

## Security notes

- Platform administration is default-deny.
- Tenant organization admin does not grant platform access.
- Platform Support Admin cannot perform Super Admin mutations.
- User suspension is enforced globally by PlatformControlMiddleware.
- Organization control is enforced when the request identifies its workspace with X-Organization-ID or X-Workspace-ID.
  Existing ForgeGov tenant resolution remains authoritative; this release intentionally does not invent a second tenant resolver.
- Administrative actions generate PlatformAuditEvent records.
- The verifier checks the full existing core test suite plus platform_admin tests.

## Release identity

Backend health, frontend package metadata, VERSION, release file, and verification all require 3.0.5.
