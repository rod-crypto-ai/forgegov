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


DOSSIER = {
    "identity": {"name": "ALPHA MISSION SYSTEMS LLC", "uei": "ALPHA123", "cage_code": "A1B2C", "state": "VA"},
    "metrics": {"award_count": 18, "obligated_amount": 7200000, "potential_amount": 12000000, "agency_count": 4, "active_awards": 3},
    "top_agencies": [{"awarding_agency": "Department of the Army", "obligated": 5200000, "award_count": 11}],
    "top_naics": [{"naics_code": "541512"}], "top_psc": [{"psc_code": "DA10"}], "vehicles": [], "recent_awards": [],
    "evidence": {"classification": "forgegov_rollup_of_official_awards", "warning": "Historical evidence does not confirm current intent."},
}


def market_fixture(route: Route) -> None:
    url = route.request.url
    if "/vendors/dossier/" in url:
        payload = DOSSIER
    elif "/vendors/compare/" in url:
        payload = {"vendors": [DOSSIER, {**DOSSIER, "identity": {**DOSSIER["identity"], "name": "BETA TECHNOLOGY INC"}}]}
    elif "/agencies/patterns/" in url:
        payload = {"agency": "Department of the Army", "metrics": {"award_count": 25, "obligated_amount": 9000000, "vendor_count": 8, "active_opportunities": 4}, "fiscal_years": [], "top_vendors": [{"recipient_name": "ALPHA MISSION SYSTEMS LLC", "award_count": 11, "obligated": 5200000}], "top_offices": [{"awarding_office": "Army Contracting Command", "obligated": 7000000}], "top_categories": [], "recent_opportunities": [], "evidence": {"warning": "Historical buying patterns."}}
    elif "/market/map/" in url:
        payload = {"category_type": "naics", "code": "541512", "categories": [], "vendors": [{"recipient_name": "ALPHA MISSION SYSTEMS LLC", "obligated": 5200000}], "agencies": [{"awarding_agency": "Department of the Army", "obligated": 9000000, "vendor_count": 8}], "relationships": [], "warning": "Stored market evidence."}
    elif "/market/vehicles/" in url:
        payload = {"metrics": {"vehicle_count": 3, "obligated_amount": 2000000, "potential_amount": 20000000}, "holders": [{"recipient_name": "ALPHA MISSION SYSTEMS LLC", "vehicle_count": 2, "obligated": 1500000, "potential": 15000000, "latest_end": "2029-09-30"}], "agencies": [], "expiring": [], "recent": [], "evidence": {"warning": "Potential value is not guaranteed spending."}}
    else:
        payload = {"results": [{"organization_id": 2, "name": "QUALIFIED PARTNER LLC", "score": 95, "reasons": ["NAICS 541512 match", "Verified ForgeGov profile"], "gaps": [], "relationship_status": "none", "verified": True, "state": "VA", "href": "/network?company=2"}], "warning": "Validate partner claims directly."}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


def run_case(browser_type, browser_name: str, scenario: tuple[str, int, int]) -> list[str]:
    name, width, height = scenario
    browser = browser_type.launch(headless=True)
    context = browser.new_context(viewport={"width": width, "height": height})
    page: Page = context.new_page()
    install_api_fixtures(page)
    page.route("**/api/intelligence/market/**", market_fixture)
    issues: list[str] = []
    try:
        page.goto(BASE_URL + "/intelligence/market", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".market-intelligence-page", timeout=15000)
        for label in ["Competitors", "Agency patterns", "Market map", "Vehicles", "Teaming"]:
            tab = page.get_by_role("tab", name=label)
            tab.click()
            if tab.get_attribute("aria-selected") != "true":
                issues.append(f"{label} tab did not expose its selected state")
        metrics = page.evaluate("() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,body:(document.body?.innerText||'').trim().length})")
        if metrics["body"] < 100:
            issues.append("market workspace became blank or near-blank")
        if metrics["sw"] > metrics["cw"] + 2:
            issues.append(f"horizontal overflow {metrics['sw']}px > {metrics['cw']}px")
    finally:
        context.close(); browser.close()
    return issues


def main() -> int:
    report = {"release": "3.2.4", "base_url": BASE_URL, "cases": {}}
    with sync_playwright() as playwright:
        browsers = {"chromium": playwright.chromium, "firefox": playwright.firefox, "webkit": playwright.webkit}
        for browser_name, browser_type in browsers.items():
            for scenario in SCENARIOS:
                key = f"{browser_name}:{scenario[0]}"
                issues = run_case(browser_type, browser_name, scenario)
                report["cases"][key] = issues
                print(f"[{'PASS' if not issues else 'FAIL'}] {key}")
    failures = {key: value for key, value in report["cases"].items() if value}
    report["passed"] = not failures
    (OUT / "v324-market-responsive-report.json").write_text(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
