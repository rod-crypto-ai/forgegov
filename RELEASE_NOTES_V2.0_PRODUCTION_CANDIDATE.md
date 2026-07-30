# ForgeGov v2.0 Production Candidate

## Production cleanup
- Updated frontend package version to 2.0.0.
- Removed unfinished generic modules from primary navigation.
- Replaced internal-development empty-state copy with user-facing guidance.
- Added a production Docker Compose override for the Next.js standalone server.
- Disabled public registration by default in Render configuration.
- Added a repeatable release-validation script.
- Added production-readiness and environment review documentation.
- Retained the completed opportunity, award, vehicle, forecast, teaming, pipeline, AI, company-profile, alert, and search workspaces.

## Deliberately hidden until completed
- Contact Groups
- Generic Government/User Files screens
- State and jurisdiction participant tables
- State/local award tables
- Generic federal grant award table
- NIGP and UNSPSC generic category tables

These routes were removed from navigation rather than exposed as unfinished product surfaces. Their backend foundations may remain for future dedicated workspaces.
