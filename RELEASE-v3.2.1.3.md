# ForgeGov v3.2.1.3 — Subcontracting Responsive UX + Visual QA

v3.2.1.3 is a focused UX stabilization release built on v3.2.1.2. It completes the subcontracting responsive-layout work before the v3.2.2 roadmap release.

## Subcontracting UX

- Replaces the congested side-by-side SUBNet/SAM layout with a tabbed intelligence feed.
- Makes the live SUBNet opportunity feed the primary view and keeps SAM subawards as supporting market intelligence.
- Rebuilds opportunity cards around a single readable content column with compact capture actions.
- Uses container queries so layout decisions are based on usable ForgeGov content width after the sidebar, not only raw browser width.
- Stacks filters, actions, workspace metrics, and detail sections progressively on laptops, tablets, phones, and zoom-equivalent widths.
- Adds stable `data-qa` hooks to the subcontracting index and detail workspace for automated layout validation.

## Cross-browser visual QA

- Adds deterministic Playwright testing for Chromium, Firefox, and WebKit.
- Covers 390, 430, 768, 1024, 1280, 1440, and 1920 pixel viewport widths.
- Adds 125% and 150% laptop zoom-equivalent viewport checks.
- Tests the actual Next.js Subcontracting index and workspace components while intercepting only API responses with stress-test fixtures.
- Fails on page horizontal overflow, component horizontal overflow, controls escaping the viewport, and undersized actionable controls.
- Captures screenshots and a JSON report under `artifacts/visual-qa/`.
- Adds a post-deployment production visual smoke command that runs the same browser/viewport matrix against `https://forge-gov.com` while intercepting API calls with safe deterministic fixtures, validating the deployed frontend without requiring production credentials or touching production records.

## Validation

The release verifier expands to 25 stages. Stage 20 is the cross-browser responsive visual-QA gate.
