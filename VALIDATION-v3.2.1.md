# ForgeGov v3.2.1 Validation

Run:

```bash
./VERIFY_V3.2.1.command
```

The 23-stage gate checks:

1. Release identity and Python compilation.
2. Release/source/production-architecture invariants.
3. Docker Compose validity.
4. Service builds.
5. Service startup.
6. Django and migration drift checks.
7. Full backend regression.
8. v3.0.7 reliability.
9. v3.0.8 data integrity/connector resilience.
10. v3.0.9 governance/cross-tenant isolation.
11. v3.1.0 launch gate.
12. v3.1.1 beta/Creator controls.
13. v3.1.2 notifications.
14. v3.1.3 capture/competitive positioning.
15. v3.2.0 Capture Copilot/Settings security.
16. v3.2.1 proposal automation/Live Web regressions.
17. Real uncached backend-to-SearXNG Live Web connectivity.
18. Frontend ESLint, TypeScript, and production build.
19. Production-style Django security check.
20. Tracked-secret, Python dependency, and npm security audit.
21. Non-root runtime checks.
22. PostgreSQL backup and isolated restore.
23. Final health/readiness and container status.

## v3.2.1 regression focus

The dedicated suite verifies:

- default response-volume/section creation and requirement traceability;
- manual revisions;
- evidence-grounded ForgeAI drafting and source guardrails;
- sanitized public Live Web query construction for private proposal and Capture Copilot prompts;
- pricing-section, pricing-revision, pricing-traceability, and reusable-pricing-content boundaries;
- proposal approval authority separate from ordinary contributor drafting rights;
- company isolation for reusable proposal content;
- package validation blockers;
- Live Web normalization/deduplication;
- exact-query cached fallback with an explicit degraded state.

Release is approved only after:

```text
[23/23] Health + readiness + container status
ForgeGov v3.2.1 validation completed successfully.
```
