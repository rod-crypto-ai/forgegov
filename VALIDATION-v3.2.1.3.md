# ForgeGov v3.2.1.3 Validation

One-time browser-QA setup:

```bash
./scripts/setup_visual_qa.sh
```

Run the full release verifier:

```bash
./VERIFY_V3.2.1.3.command
```

The release is cleared only when all 25 stages pass and the verifier ends with:

```text
ForgeGov v3.2.1.3 validation completed successfully.
```

The responsive stage must pass Chromium, Firefox, and WebKit across the required phone, tablet, laptop, desktop, and zoom-equivalent viewport matrix with no horizontal overflow or undersized controls.

After the Render deployment is live, run the same matrix against the **actual deployed ForgeGov frontend bundle** (API calls are intercepted with deterministic stress fixtures, so this does not require a production user or touch production data):

```bash
./scripts/visual_qa_production.sh
```

Production screenshots and the JSON report are written to `artifacts/visual-qa-production/`. Do not call the responsive production work complete until this deployed-site pass is clean.
