#!/usr/bin/env python3
"""Shared geometry, theme, and federal-feed ordering regression with isolated fixtures.

These are UI tests, not evidence that live government providers are healthy.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright
from visual_qa_subcontracting import install_api_fixtures

BASE_URL = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3100").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", "artifacts/visual-qa")) / "experience"
OUT.mkdir(parents=True, exist_ok=True)
SCENARIOS = [("phone", 390, 844), ("tablet", 768, 1024), ("landscape", 1024, 768), ("desktop", 1440, 900), ("wide", 1920, 1080)]


def fulfill(route, payload, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def feed(kind):
    row = {"id": 1, "source_id": "qa-opportunity", "title": "SAM controlled opportunity", "agency": "QA Agency", "posted_date": "2026-10-22", "naics_code": "541512"}
    if kind == "awards":
        row = {"id": 2, "source_id": "qa-award", "description": "USAspending controlled award", "recipient_name": "QA Recipient", "obligated_amount": 2000000, "start_date": "2025-10-22"}
    return {"kind": kind, "count": 1, "page": 1, "page_size": 20, "total_pages": 1, "next_page": None, "previous_page": None, "results": [row], "sync": {"status": "partial", "last_completed_at": "2026-10-22T00:00:00Z", "records_seen": 1}}


def install(page, theme):
    install_api_fixtures(page)
    page.route("**/api/settings/preferences/**", lambda r: fulfill(r, {"theme": theme, "density": "comfortable"}))
    page.route("**/api/dashboard/summary/**", lambda r: fulfill(r, {"pursuits": {"total": 0, "by_stage": {}}, "opportunities": {"active": 12, "total": 20}, "awards": {"total": 4}, "tasks": {"open": 0, "overdue": 0}}))
    command = {"metrics": {"weighted_pipeline": 0}, "deadlines": [], "activity": [], "insights": [], "quick_actions": [], "intelligence": {"connectors": {"healthy": 1, "verified": 1, "total": 2, "attention": 1}, "recent_awards_30d": 0, "latest_award_sync_status": "failed", "latest_award_sync": "2026-10-22T00:00:00Z", "federal_activity": {"opportunities": [{"source_id": "qa", "title": "Long opportunity title " * 5, "agency": "QA Agency", "posted_date": "2026-10-22"}], "awards": []}}}
    page.route("**/api/dashboard/command-center/**", lambda r: fulfill(r, command))
    page.route("**/api/integrations/status/**", lambda r: fulfill(r, {"sam_gov": {"configured": True}, "usaspending": {"reachable": False, "stored_awards": 4}, "ai": {"web_search_configured": False}}))
    page.route("**/api/intelligence/recent-federal-activity/**", lambda r: fulfill(r, feed(parse_qs(urlparse(r.request.url).query)["kind"][0])))


def geometry(page):
    return page.evaluate("""() => {
      const root = document.documentElement;
      const control = document.querySelector('.federal-feed-controls');
      const rect = control?.getBoundingClientRect();
      const tab = control?.querySelector('[role=tab]')?.getBoundingClientRect();
      return {overflow: root.scrollWidth - root.clientWidth,
        heading: parseFloat(getComputedStyle(document.querySelector('h1')).fontSize),
        feedInset: rect && tab ? tab.left - rect.left : null,
        panels: [...document.querySelectorAll('.command-center-grid > .command-panel')].map(e => ({height:e.getBoundingClientRect().height, minHeight:getComputedStyle(e).minHeight})),
        surface: getComputedStyle(root).getPropertyValue('--surface').trim(),
        panelColor: document.querySelector('.data-panel, .command-panel') ? getComputedStyle(document.querySelector('.data-panel, .command-panel')).backgroundColor : null};
    }""")


def run_case(browser, engine, name, width, height, theme):
    context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme)
    page = context.new_page()
    install(page, theme)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(BASE_URL + "/", wait_until="networkidle")
        page.locator(".dashboard-federal-preview").wait_for()
        dashboard = geometry(page)
        assert dashboard["overflow"] <= 2, dashboard
        assert dashboard["heading"] <= 36, dashboard
        assert all(p["height"] < 250 for p in dashboard["panels"]), dashboard
        assert dashboard["surface"], "shared surface token is undefined"
        if theme == "dark":
            assert dashboard["panelColor"] != "rgb(255, 255, 255)", dashboard
        page.screenshot(path=str(OUT / f"{engine}-{name}-{theme}-dashboard.png"), full_page=True)
        page.goto(BASE_URL + "/opportunities/recent-federal-activity", wait_until="networkidle")
        page.get_by_role("heading", name="SAM controlled opportunity", exact=True).wait_for()
        metrics = geometry(page)
        assert metrics["overflow"] <= 2, metrics
        assert metrics["feedInset"] >= 14, metrics
        page.screenshot(path=str(OUT / f"{engine}-{name}-{theme}-feed.png"), full_page=True)
        page.get_by_role("tab", name="USAspending awards", exact=True).click()
        page.get_by_role("heading", name="USAspending controlled award", exact=True).wait_for()
        assert page.get_by_text("SAM controlled opportunity", exact=True).count() == 0

        # Hold the older SAM request until the newer USAspending response has rendered.
        pending = []
        def out_of_order(route):
            kind = parse_qs(urlparse(route.request.url).query)["kind"][0]
            if kind == "opportunities":
                pending.append(route)
            else:
                fulfill(route, feed(kind))
        page.route("**/api/intelligence/recent-federal-activity/**", out_of_order)
        with page.expect_request("**/api/intelligence/recent-federal-activity/?kind=opportunities&*"):
            page.get_by_role("tab", name="SAM.gov opportunities", exact=True).click()
        page.get_by_role("tab", name="USAspending awards", exact=True).click()
        page.get_by_role("heading", name="USAspending controlled award", exact=True).wait_for()
        assert pending, "older request was not held"
        for route in pending:
            fulfill(route, feed("opportunities"))
        page.wait_for_timeout(150)
        assert page.get_by_role("heading", name="USAspending controlled award", exact=True).is_visible()
        assert page.get_by_text("SAM controlled opportunity", exact=True).count() == 0

        # Failed source switch must never retain rows or counts from the prior source.
        page.route("**/api/intelligence/recent-federal-activity/**", lambda r: fulfill(r, {"detail": "Controlled source failure"}, 503))
        page.get_by_role("tab", name="SAM.gov opportunities", exact=True).click()
        page.get_by_role("alert").filter(has_text="Controlled source failure").wait_for()
        assert page.locator(".federal-feed-card").count() == 0
        assert page.get_by_text("1 synchronized record", exact=True).count() == 0
        assert not errors, errors
        return {"passed": True, "dashboard": dashboard, "feed": metrics}
    except Exception as error:
        page.screenshot(path=str(OUT / f"{engine}-{name}-{theme}-failure.png"), full_page=True)
        return {"passed": False, "error": str(error), "page_errors": errors}
    finally:
        context.close()


def main():
    report = {"scope": "isolated UI fixtures; not live provider validation", "cases": {}}
    with sync_playwright() as p:
        for engine in ("chromium", "firefox", "webkit"):
            browser = getattr(p, engine).launch()
            try:
                for name, width, height in SCENARIOS:
                    for theme in ("light", "dark"):
                        key = f"{engine}-{name}-{theme}"
                        result = run_case(browser, engine, name, width, height, theme)
                        report["cases"][key] = result
                        print(f"{'PASS' if result['passed'] else 'FAIL'} {key}: {result.get('error', '')}", flush=True)
            finally:
                browser.close()
    report["passed"] = all(case["passed"] for case in report["cases"].values())
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
