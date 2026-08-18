# ForgeGov v3.1.0 — Private Beta Readiness & Production Launch Gate

## Release focus
ForgeGov v3.1.0 is the private-beta launch gate. It validates the full product surface built through v3.0.9 rather than introducing a new platform subsystem.

## Included
- Full regression chain for identity/security, reliability/recovery, connector integrity, and enterprise governance.
- Production-style Django deployment security check.
- Python and frontend dependency vulnerability audits.
- Tracked-secret and moving-migration dependency checks.
- Backup creation and isolated restore verification.
- Health/readiness and non-root runtime verification.
- Launch-critical API route resolution tests for login, registration, recovery, security, governance, saved searches, and pipeline intake.
- State dropdown for SAM.gov federal opportunity search, including U.S. states, District of Columbia, and territories.
- Matching State dropdown in the State & Local procurement-source workspace.
- Cleanup of stale connector placeholder copy in opportunity search.

## Database
No new database migration is required for v3.1.0.

## Release gate
Run `./VERIFY_V3.1.0.command`. Do not commit, push, or tag until all launch-gate stages pass.
