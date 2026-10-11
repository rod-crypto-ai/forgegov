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


PAYLOAD = {
    "definitions": {"active_pursuit": "Triage through Submitted.", "pipeline_value": "Sum of active pursuit estimated values.", "weighted_pipeline": "Active pursuit estimated value multiplied by entered probability of win.", "stale": "No update for 14 days."},
    "summary": {"active_pursuits": 2, "pipeline_value": "2500000", "weighted_pipeline": "1225000", "overdue": 1, "due_within_14_days": 1, "stale": 1, "unassigned": 1, "unlinked_pipeline_items": 1},
    "pursuits": [{
        "id": 1, "title": "Enterprise Mission Support", "stage": "capture", "owner_name": "Capture Owner", "estimated_value": "2500000", "probability_of_win": 49, "weighted_value": "1225000", "due_date": "2026-11-01T12:00:00Z", "next_action": "Complete customer review", "age_days": 28, "stale_days": 4, "agency": "Department of the Navy", "gate_findings": [], "allowed_transitions": ["proposal", "no_bid", "archived"],
        "plan": {"id": 1, "status": "active", "template_key": "standard", "objective": "Win and perform safely", "customer_need": "Mission continuity", "win_strategy": "Evidence-led transition", "key_risks": [], "progress_percent": 50, "milestones": [
            {"id": 1, "title": "Confirm customer need and acquisition fit", "category": "qualification", "required": True, "completed_at": "2026-10-01T12:00:00Z", "blocked": False, "owner_name": "Capture Owner"},
            {"id": 2, "title": "Complete evidence-backed bid / no-bid review", "category": "decision", "required": True, "completed_at": None, "blocked": False, "owner_name": "Capture Owner"},
        ]},
    }],
    "review_queue": [{"pursuit_id": 1, "title": "Enterprise Mission Support", "urgency": 60, "signals": ["Due within 14 days"]}],
    "workload": [{"owner_id": 1, "owner_name": "Capture Owner", "pursuits": 2, "open_tasks": 4, "overdue_tasks": 1}],
    "agency_concentration": [{"agency": "Department of the Navy", "value": "2500000", "share_percent": 100}],
    "weekly_review": {"id": 1, "week_start": "2026-10-12", "status": "draft", "notes": "Review priority pursuits.", "decisions": []},
    "recent_changes": [{"id": 1, "title": "Enterprise Mission Support", "previous_stage": "qualify", "new_stage": "capture", "previous_probability": 35, "new_probability": 49, "reason": "Bid approved", "changed_by": "Capture Owner", "created_at": "2026-10-11T12:00:00Z"}],
    "templates": [{"key": "standard", "name": "Standard", "milestone_count": 6}, {"key": "accelerated", "name": "Accelerated", "milestone_count": 4}],
}


def fixture(route: Route) -> None:
    route.fulfill(status=200, content_type="application/json", body=json.dumps(PAYLOAD))


def run_case(browser_type, scenario: tuple[str, int, int]) -> list[str]:
    name, width, height = scenario
    browser = browser_type.launch(headless=True)
    context = browser.new_context(viewport={"width": width, "height": height})
    page: Page = context.new_page()
    install_api_fixtures(page)
    page.route("**/api/capture/operations/**", fixture)
    issues: list[str] = []
    try:
        page.goto(BASE_URL + "/capture/operations", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".capture-ops-page", timeout=15000)
        page.get_by_text("Enterprise Mission Support", exact=True).first.wait_for(timeout=15000)
        for label in ["Active pursuits", "Weekly capture review", "Enterprise Mission Support", "Agency exposure"]:
            if page.get_by_text(label, exact=False).count() == 0:
                issues.append(f"missing visible content: {label}")
        metrics = page.evaluate("() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,body:(document.body?.innerText||'').trim().length})")
        if metrics["body"] < 300:
            issues.append("capture operations workspace became blank or near-blank")
        if metrics["sw"] > metrics["cw"] + 2:
            issues.append(f"horizontal overflow {metrics['sw']}px > {metrics['cw']}px")
    finally:
        context.close(); browser.close()
    return issues


def main() -> int:
    report = {"release": "3.2.5", "base_url": BASE_URL, "cases": {}}
    with sync_playwright() as playwright:
        for browser_name, browser_type in {"chromium": playwright.chromium, "firefox": playwright.firefox, "webkit": playwright.webkit}.items():
            for scenario in SCENARIOS:
                key = f"{browser_name}:{scenario[0]}"
                issues = run_case(browser_type, scenario)
                report["cases"][key] = issues
                print(f"[{'PASS' if not issues else 'FAIL'}] {key}{f': {issues}' if issues else ''}")
    failures = {key: value for key, value in report["cases"].items() if value}
    report["passed"] = not failures
    (OUT / "v325-capture-operations-responsive-report.json").write_text(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
