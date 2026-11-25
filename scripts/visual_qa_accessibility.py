#!/usr/bin/env python3
"""Check rendered workspace contrast and accessible controls with synthetic data."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from visual_qa_experience import fulfill, install, navigate


ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3100").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", "artifacts/visual-qa")) / "accessibility"
AXE = ROOT / "frontend/node_modules/axe-core/axe.min.js"
ROUTES = {
    "/": "ForgeGov command center",
    "/capture/tasks": "Tasks",
    "/capture/pipelines": "Pipelines",
    "/project-rooms": "Project Rooms",
    "/opportunities/recent-federal-activity": "Recent Federal Activity",
    "/audit-log": "Audit log",
    "/settings": "Settings",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    options = {}
    if os.getenv("FORGEGOV_QA_CHROMIUM_PATH"):
        options = {"executable_path": os.environ["FORGEGOV_QA_CHROMIUM_PATH"], "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**options)
        for width in (390, 1440):
            for theme in ("light", "dark"):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                page = context.new_page()
                install(page, theme)
                page.route("**/api/audit-logs/**", lambda route: fulfill(route, []))
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for path, heading in ROUTES.items():
                    navigate(page, BASE + path, wait_until="networkidle")
                    page.get_by_role("heading", level=1).wait_for()
                    if path == "/":
                        page.locator(".dashboard-federal-preview").wait_for()
                    page.add_script_tag(path=str(AXE))
                    violations = page.evaluate("""async () => {
                      const result = await axe.run(document, {
                        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}
                      });
                      return result.violations.map(violation => ({
                        id: violation.id, impact: violation.impact,
                        nodes: violation.nodes.map(node => ({target: node.target, summary: node.failureSummary}))
                      }));
                    }""")
                    row = {"path": path, "theme": theme, "width": width, "violations": violations}
                    results.append(row)
                    if violations:
                        page.screenshot(path=str(OUT / f"{width}-{theme}-{heading.lower().replace(' ', '-')}.png"), full_page=True)
                    print(f"{'FAIL' if violations else 'PASS'} accessibility {width} {theme} {path}", flush=True)
                assert not errors, errors
                context.close()
        browser.close()
    (OUT / "report.json").write_text(json.dumps(results, indent=2))
    assert all(not row["violations"] for row in results), "Accessibility violations found. See the report."


if __name__ == "__main__":
    main()
