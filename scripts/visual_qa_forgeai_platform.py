#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from playwright.sync_api import Page, Route, sync_playwright
except ImportError:
    print("Playwright is not installed. Run ./scripts/setup_visual_qa.sh first.", file=sys.stderr)
    raise SystemExit(2)

from visual_qa_subcontracting import install_api_fixtures


BASE_URL = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", "artifacts/visual-qa"))
OUT.mkdir(parents=True, exist_ok=True)
SCENARIOS = [
    ("phone-390", 390, 844), ("phone-430", 430, 932), ("tablet-portrait", 768, 1024),
    ("tablet-landscape", 1024, 768), ("laptop-1280", 1280, 800),
    ("desktop-1440", 1440, 900), ("desktop-1920", 1920, 1080),
]


PLATFORM = {
    "release": "3.2.6",
    "workflows": [
        {"key": "research", "label": "Research"}, {"key": "opportunity", "label": "Opportunity"},
        {"key": "capture", "label": "Capture"}, {"key": "proposal", "label": "Proposal"},
        {"key": "market", "label": "Market"},
    ],
    "source_inventory": {"active_opportunities": 22, "stored_awards": 45, "workspace_pursuits": 3, "workspace_files": 8, "project_rooms": 2, "proposal_plans": 1, "company_profile": "available"},
    "governance": {"organization_scoped": True, "source_provenance_recorded": True, "autonomous_record_changes": False, "human_review_required": True},
    "recent_runs": [],
}
ANSWER = {
    "answer": "Verified Evidence\nMission support is recorded in the official opportunity [OPP-1].\n\nAnalysis and Inferences\nThe fit appears plausible but requires validation.\n\nRisks and Unknowns\nStaffing evidence is incomplete.\n\nRecommended Next Actions\nValidate staffing and the response deadline.",
    "model": "qa-model",
    "provider": "openai",
    "conversation_id": 1,
    "research_run_id": 1,
    "workflow": "opportunity",
    "sources": [{"label": "[OPP-1]", "type": "opportunity", "title": "Mission Support", "url": "https://sam.gov", "classification": "official"}],
    "evidence_summary": {"source_count": 1, "classifications": {"official": 1}, "source_types": {"opportunity": 1}, "coverage_note": "Source counts show what was supplied to the model; they do not independently verify completeness or correctness."},
    "web_enabled": False, "web_configured": True, "web_status": "unavailable",
}


def fulfill(payload):
    def handler(route: Route) -> None:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
    return handler


def run_case(browser_type, scenario: tuple[str, int, int]) -> list[str]:
    name, width, height = scenario
    browser = browser_type.launch(headless=True)
    context = browser.new_context(viewport={"width": width, "height": height})
    page: Page = context.new_page()
    install_api_fixtures(page)
    page.route("**/api/auth/csrf/**", fulfill({"csrfToken": "forgegov-visual-qa"}))
    page.route("**/api/ai/platform/**", fulfill(PLATFORM))
    page.route("**/api/ai/conversations/**", fulfill([]))
    page.route("**/api/ai/chat/**", fulfill(ANSWER))
    page.route("**/api/integrations/status/**", fulfill({"ai": {"provider": "openai", "model": "qa-model", "configured": True, "web_search_configured": True, "web_search_reachable": False, "web_search_status": "unavailable"}}))
    issues: list[str] = []
    try:
        page.goto(BASE_URL + "/assistant", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".modern-ai-layout", timeout=15000)
        page.get_by_text("FORGEAI INTELLIGENCE PLATFORM", exact=False).wait_for(timeout=15000)
        page.locator(".ai-workflow-select select").select_option("opportunity")
        page.locator(".assistant-composer textarea").fill("Assess the mission support opportunity")
        page.get_by_role("button", name="Send").click()
        page.get_by_text("Verified Evidence", exact=True).wait_for(timeout=15000)
        for label in ["ForgeGov AI", "Verified Evidence", "Evidence and provenance", "Evidence is assistance, not approval"]:
            if page.get_by_text(label, exact=False).count() == 0:
                issues.append(f"missing visible content: {label}")
        metrics = page.evaluate("() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,body:(document.body?.innerText||'').trim().length})")
        if metrics["body"] < 400:
            issues.append("ForgeAI workspace became blank or near-blank")
        if metrics["sw"] > metrics["cw"] + 2:
            issues.append(f"horizontal overflow {metrics['sw']}px > {metrics['cw']}px")
    finally:
        context.close(); browser.close()
    return issues


def main() -> int:
    report = {"release": "3.2.6", "base_url": BASE_URL, "cases": {}}
    with sync_playwright() as playwright:
        for browser_name, browser_type in {"chromium": playwright.chromium, "firefox": playwright.firefox, "webkit": playwright.webkit}.items():
            for scenario in SCENARIOS:
                key = f"{browser_name}:{scenario[0]}"
                issues = run_case(browser_type, scenario)
                report["cases"][key] = issues
                print(f"[{'PASS' if not issues else 'FAIL'}] {key}{f': {issues}' if issues else ''}")
    failures = {key: value for key, value in report["cases"].items() if value}
    report["passed"] = not failures
    (OUT / "v326-forgeai-platform-responsive-report.json").write_text(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
