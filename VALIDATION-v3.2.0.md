# ForgeGov v3.2.0 Validation

Release verification is performed with:

```bash
./VERIFY_V3.2.0.command
```

The 21-stage gate checks release identity, source invariants, Docker Compose, builds, migrations, all historical regression suites, the v3.2.0 Capture Copilot/Settings tests, frontend lint/typecheck/build, Django deployment security, secret/dependency audits, non-root runtime, PostgreSQL backup/isolated restore, and final health/readiness.

## v3.2.0 regression focus

The dedicated suite verifies:

- persistent and validated user appearance/AI preferences;
- preference isolation between users;
- private workspace grounding opt-out;
- financial-value exclusion from non-financial AI grounding;
- deterministic Capture Copilot posture;
- persisted and reusable Copilot analysis;
- Viewer read-only behavior;
- non-financial Copilot economics redaction;
- non-financial Copilot prompt/cache scope;
- workspace-grounding opt-out in the custom Copilot evidence payload;
- historical financial Copilot output is hidden when a user loses financial access.

Release is approved only after the verifier ends with:

```text
[21/21] Health + readiness + container status
ForgeGov v3.2.0 validation completed successfully.
```
