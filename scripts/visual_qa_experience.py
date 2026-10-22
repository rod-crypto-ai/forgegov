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


def capture_workflows(page, evidence_key):
    """Check actual rendered mutations against disposable HTTP fixtures."""
    tasks = []
    writes = []
    page.route("**/api/auth/csrf/**", lambda route: fulfill(route, {"csrfToken": "isolated-ui-qa"}))
    page.route("**/api/tasks/?*", lambda route: fulfill(route, {"results": tasks}))
    def create_task(route):
        body = route.request.post_data_json
        writes.append(body)
        tasks.append({"id": 1, "title": body["title"], "due_at": body["due_at"], "completed": False})
        fulfill(route, tasks[0], 201)
    page.route("**/api/workflow/tasks/", create_task)
    page.goto(BASE_URL + "/capture/tasks", wait_until="networkidle")
    page.get_by_text("No tasks yet", exact=True).wait_for()
    page.get_by_label("Task title", exact=True).fill("QA capture action")
    page.get_by_label("Due date (your local time)", exact=True).fill("2026-11-02T09:00")
    page.get_by_role("button", name="Add task", exact=True).click()
    page.get_by_text("QA capture action", exact=True).wait_for()
    assert len(writes) == 1
    assert writes[0]["due_at"] == "2026-11-02T00:00:00.000Z", writes
    page.route("**/api/tasks/1/", lambda route: fulfill(route, {"detail": "Controlled task rejection"}, 503))
    page.get_by_role("button", name="Complete: QA capture action", exact=True).click()
    page.get_by_role("alert").filter(has_text="Controlled task rejection").wait_for()
    assert page.get_by_role("button", name="Complete: QA capture action", exact=True).get_attribute("aria-pressed") == "false"
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-task-error.png"), full_page=True)
    page.route("**/api/saved-searches/?*", lambda route: fulfill(route, {"results": []}))
    page.goto(BASE_URL + "/capture/saved-searches", wait_until="networkidle")
    page.get_by_text("No saved searches yet", exact=True).wait_for()
    assert page.get_by_role("link", name="Find opportunities", exact=True).is_visible()


def pursuit_rooms_and_audit(page, evidence_key):
    pursuits = [{"id": 7, "title": "QA retained pursuit", "stage": "lost", "probability_of_win": 25, "estimated_value": "100000", "due_date": "2026-11-02T00:00:00Z", "next_action": "Review outcome"}]
    page.route("**/api/pursuits/?*", lambda route: fulfill(route, {"results": pursuits}))
    def update_pursuit(route):
        if route.request.post_data_json.get("stage") == "proposal":
            fulfill(route, {"detail": "Controlled pursuit rejection"}, 503)
        else:
            pursuits[0].update(route.request.post_data_json)
            fulfill(route, pursuits[0])
    page.route("**/api/pursuits/7/", update_pursuit)
    page.goto(BASE_URL + "/capture/pursuits", wait_until="networkidle")
    opener = page.get_by_role("button", name="Open pursuit: QA retained pursuit", exact=True)
    opener.wait_for()
    stage = page.get_by_label("Stage: QA retained pursuit", exact=True)
    assert stage.input_value() == "lost"
    stage.select_option("proposal")
    page.get_by_role("alert").filter(has_text="Controlled pursuit rejection").wait_for()
    assert stage.input_value() == "lost"
    opener.click()
    dialog = page.get_by_role("dialog", name="QA retained pursuit", exact=True)
    dialog.wait_for()
    assert dialog.get_by_label("Due date", exact=True).input_value() == "2026-11-02T09:00"
    dialog.press("Escape")
    dialog.wait_for(state="hidden")
    # Closed outcomes remain recoverable on the board after a successful move.
    stage.select_option("archived")
    page.locator(".kanban-column").filter(has=page.locator("header").filter(has_text="Archived")).get_by_role("button", name="Open pursuit: QA retained pursuit", exact=True).wait_for()
    assert geometry(page)["overflow"] <= 2
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-pursuits.png"), full_page=True)
    rooms = []
    page.route("**/api/project-rooms/?*", lambda route: fulfill(route, {"results": rooms}))
    def create_room(route):
        if route.request.method != "POST":
            fulfill(route, {"results": rooms})
            return
        rooms.append({"id": 9, **route.request.post_data_json, "owner_organization_name": "QA Company", "partners": []})
        fulfill(route, rooms[0], 201)
    page.route("**/api/project-rooms/", create_room)
    page.goto(BASE_URL + "/project-rooms", wait_until="networkidle")
    page.get_by_text("No Project Rooms yet", exact=True).wait_for()
    page.get_by_label("Room name", exact=True).fill("QA secure room")
    page.get_by_role("button", name="Create Project Room", exact=True).click()
    page.get_by_role("link", name="QA secure room", exact=True).wait_for()
    page.get_by_role("status").filter(has_text="Project Room created.").wait_for()
    if page.locator("html").get_attribute("data-theme") == "dark":
        for selector in (".release-four-summary > div", ".source-health-pill", ".inline-message"):
            colors = page.locator(selector).evaluate_all("es=>es.map(e=>({background:getComputedStyle(e).backgroundColor,color:getComputedStyle(e).color}))")
            assert colors and all(c["background"] != "rgb(255, 255, 255)" and c["background"] != c["color"] for c in colors), {selector: colors}
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-rooms.png"), full_page=True)
    events = [{"id": i, "action": f"security.qa_event_{i}", "object_type": "workspace", "object_id": "1", "actor_name": "QA Owner", "created_at": "2026-10-22T00:00:00Z"} for i in range(26)]
    page.route("**/api/audit-logs/**", lambda route: fulfill(route, events))
    page.goto(BASE_URL + "/audit-log", wait_until="networkidle")
    page.get_by_text("Page 1 of 2 · 26 loaded events", exact=True).wait_for()
    assert page.locator(".simple-row").count() == 25
    page.get_by_role("button", name="Next", exact=True).click()
    page.get_by_text("security.qa_event_25", exact=True).wait_for()
    assert page.locator(".simple-row").count() == 1
    page.get_by_label("Filter loaded events", exact=True).fill("no-match")
    page.get_by_text("No matching audit events", exact=True).wait_for()
    assert geometry(page)["overflow"] <= 2


def proposal_editing(page, evidence_key):
    notice = "qa-proposal-workflow"
    section = {"id": 1, "key": "technical", "title": "QA technical section", "section_type": "technical", "instructions": "Use evidence", "content": "Saved proposal baseline", "status": "drafting", "owner_id": None, "owner": "", "due_at": None, "sort_order": 1, "approved_at": None, "approved_by": "", "revision_count": 1, "restricted": False, "requirement_links": []}
    second = {**section, "id": 2, "title": "QA management section", "content": "Saved management baseline"}
    counts = {"volumes": 1, "sections": 2, "sections_approved": 0, "requirements": 0, "requirements_closed": 0, "reviews": 0, "reviews_passed": 0, "open_findings": 0}
    payload = {"plan": {"id": 1, "status": "draft", "submission_ready": False, "readiness_score": 0}, "execution": {"members": [], "requirements": [], "counts": {"requirements_total": 0, "requirements_closed": 0, "reviews_total": 0, "reviews_passed": 0, "open_findings": 0}, "amendment_impact": {"changed": False, "changes": []}}, "volumes": [{"id": 1, "key": "technical", "title": "QA technical volume", "instructions": "", "status": "draft", "owner_id": None, "owner": "", "due_at": None, "page_limit": None, "sort_order": 1, "sections": [section, second]}], "library": [], "package_validation": {"ready": False, "blockers": ["Human review required"], "warnings": [], "counts": counts, "checked_at": "2026-10-22T00:00:00Z"}, "permissions": {"can_financial": True, "can_approve": True}, "warning": "QA controlled proposal evidence"}
    detail = {"opportunity": {"title": "QA proposal opportunity", "fullParentPathName": "QA Agency", "solicitationNumber": "QA-PROPOSAL", "type": "Solicitation", "naicsCode": "541512"}, "description": "QA scope", "documents": [], "source_url": "https://sam.gov/"}
    page.route(f"**/api/live/sam/opportunities/{notice}/", lambda route: fulfill(route, detail))
    for pattern in ("**/api/workflow/opportunity-workspaces/**", "**/api/workflow/opportunities/*/command-summary/**", "**/api/intelligence/opportunities/**"):
        page.route(pattern, lambda route: fulfill(route, {"detail": "No controlled supplemental evidence"}, 404))
    def production(route):
        if route.request.method == "POST":
            fulfill(route, {"detail": "Controlled proposal structure rejection"}, 503)
        else:
            fulfill(route, payload)
    page.route(f"**/api/ai/opportunities/{notice}/proposal-production/", production)
    def save_section(route):
        section.update(route.request.post_data_json)
        section["revision_count"] += 1
        fulfill(route, payload)
    page.route(f"**/api/ai/opportunities/{notice}/proposal-sections/1/", save_section)
    page.goto(BASE_URL + f"/opportunities/federal-contracts/{notice}", wait_until="networkidle")
    page.get_by_role("tab", name="Proposal", exact=True).click()
    editor = page.get_by_label("Section content", exact=True)
    editor.wait_for()
    page.wait_for_function("document.querySelector('.proposal-section-editor')?.value === 'Saved proposal baseline'")
    editor.fill("Unsaved proposal work must survive")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button").filter(has_text="QA management section").click()
    assert editor.input_value() == "Unsaved proposal work must survive"
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("tab", name="Overview", exact=True).click()
    assert editor.is_visible() and editor.input_value() == "Unsaved proposal work must survive"
    page.get_by_role("button", name="Save section", exact=True).click()
    page.get_by_role("status").filter(has_text="Section saved and revision recorded.").wait_for()
    assert section["content"] == "Unsaved proposal work must survive"
    page.get_by_role("button").filter(has_text="QA management section").click()
    page.wait_for_function("document.querySelector('.proposal-section-editor')?.value === 'Saved management baseline'")
    page.once("dialog", lambda dialog: dialog.accept("QA additional volume"))
    page.get_by_role("button", name="Add volume", exact=True).click()
    page.get_by_role("status").filter(has_text="Controlled proposal structure rejection").wait_for()
    assert editor.input_value() == "Saved management baseline"
    assert geometry(page)["overflow"] <= 2
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-proposal.png"), full_page=True)


def sam_award_pages(page, evidence_key):
    requests = []
    def awards(route):
        params = parse_qs(urlparse(route.request.url).query)
        offset = int(params.get("offset", ["0"])[0])
        kind = params["record_type"][0]
        requests.append((kind, offset))
        fulfill(route, {"total_records": 101, "limit": 100, "offset": offset, "results": [{"title": f"QA {kind} {offset}", "recipient_name": "=1+1", "piid": f"PIID-{offset}", "award_type": "IDIQ", "awarding_agency": "QA Agency", "referenced_idv": "QA-PARENT", "date_signed": "2020-10-01", "dollars_obligated": 1000}]})
    page.route("**/api/live/sam/contract-awards/**", awards)
    for kind, path in [("idv", "/awards/federal-idv"), ("vehicles", "/awards/federal-vehicles")]:
        page.goto(BASE_URL + path, wait_until="networkidle")
        page.get_by_text(f"QA {kind} 0", exact=True).wait_for()
        assert page.get_by_text("Page 1 · 101 source matches", exact=True).is_visible()
        page.locator(".award-record-details summary").click()
        page.get_by_text("QA-PARENT", exact=True).wait_for()
        page.get_by_role("button", name="Next", exact=True).click()
        page.get_by_text(f"QA {kind} 100", exact=True).wait_for()
        page.get_by_text("Page 2 · 101 source matches", exact=True).wait_for()
        assert not page.get_by_role("button", name="Next", exact=True).is_enabled()
        with page.expect_download() as download:
            page.get_by_role("button", name="Export", exact=True).click()
        assert "'=1+1" in Path(download.value.path()).read_text(), "spreadsheet formulas must be neutralized"
        assert geometry(page)["overflow"] <= 2
        if evidence_key:
            page.screenshot(path=str(OUT / f"{evidence_key}-{kind}-awards.png"), full_page=True)
    assert ("idv", 100) in requests and ("vehicles", 0) in requests, requests


def reports_and_company(page, evidence_key):
    def report_response(route):
        query = parse_qs(urlparse(route.request.url).query)
        kind = query["kind"][0]
        current_page = int(query["page"][0])
        rows = [{"awarding_agency": "QA Agency", "recipient_name": "QA Entrant", "recipient_uei": "QAUEI", "first_award": "2026-10-01", "latest_award": "2026-10-20", "award_count": 2, "obligated": 1000000, "recipients": 1, "share_percent": 100}]
        fulfill(route, {"kind": kind, "source": "USAspending.gov", "generated_at": "2026-10-22T00:00:00Z", "coverage_note": "Stored federal award history only, not a live market total.", "count": 26, "page": current_page, "total_pages": 2, "results": rows, "totals": {"records": 2, "obligated": 1000000, "latest_source_update": None}, "sync": {"status": "failed", "last_completed_at": "2026-10-22T00:00:00Z"}})
    page.route("**/api/reports/market/**", report_response)
    for kind, heading in [("funding", "Agency funding distribution"), ("new-entrants", "First observed recipient–agency relationships")]:
        page.goto(BASE_URL + "/reports/" + kind, wait_until="networkidle")
        page.get_by_role("heading", name=heading, exact=True).wait_for()
        page.locator(".data-table tbody tr").wait_for()
        assert geometry(page)["overflow"] <= 2
        assert page.locator(".pagination-bar").evaluate("e=>getComputedStyle(e).position") != "sticky"
        assert page.get_by_text("Stored federal award history only, not a live market total.", exact=True).is_visible()
        if evidence_key:
            page.screenshot(path=str(OUT / f"{evidence_key}-{kind}.png"), full_page=True)
        page.get_by_role("button", name="Next", exact=True).click()
        page.get_by_text("Page 2 of 2", exact=True).wait_for()
        with page.expect_download() as download:
            page.get_by_role("button", name="Export current page", exact=True).click()
        assert download.value.suggested_filename == kind + "-page-2.csv"
    profile = {key: "" for key in ("organization_name", "uei", "cage_code", "tagline", "description", "website", "city", "state", "country", "contact_email")}
    profile.update({key: [] for key in ("naics_codes", "psc_codes", "capabilities", "certifications", "contract_vehicles", "service_areas")})
    profile.update({"organization_name": "QA Company", "is_public": False, "accepting_partners": False})
    page.route("**/api/network/profile/**", lambda route: fulfill(route, profile))
    for pattern in ("**/api/team/members/**", "**/api/team/invitations/**", "**/api/network/connections/**", "**/api/company/join-requests/**"):
        page.route(pattern, lambda route: fulfill(route, []))
    page.goto(BASE_URL + "/company", wait_until="networkidle")
    page.locator(".company-hub-form").wait_for()
    inputs = page.locator('.invite-company-form input').evaluate_all("es => es.map(e=>({height:e.getBoundingClientRect().height,radius:parseFloat(getComputedStyle(e).borderRadius)}))")
    assert inputs and all(value["height"] >= 40 and value["radius"] >= 8 for value in inputs), inputs
    if page.locator("html").get_attribute("data-theme") == "dark":
        assert page.locator(".workspace-summary > div").first.evaluate("e=>getComputedStyle(e).backgroundColor") != "rgb(255, 255, 255)"
    page.get_by_text("No employee invitations", exact=True).wait_for()
    assert geometry(page)["overflow"] <= 2
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-company.png"), full_page=True)
    page.route("**/api/intelligence/forecasts/sources/**", lambda route: fulfill(route, {"status": "fallback", "reachable": False, "results": [{"agency": "QA Agency", "forecast_url": "https://www.acquisition.gov/procurement-forecasts", "description": "Official directory reference"}], "warning": "Directory snapshot; source refresh unavailable."}))
    page.goto(BASE_URL + "/opportunities/federal-forecasts", wait_until="networkidle")
    page.get_by_text("Directory reference", exact=True).wait_for()
    assert page.get_by_text("Active", exact=True).count() == 0
    page.get_by_role("button", name="View source details", exact=False).click()
    page.get_by_text("Directory link, not a live notice", exact=True).wait_for()
    page.get_by_role("button", name="Close forecast source", exact=True).click()
    if evidence_key:
        page.screenshot(path=str(OUT / f"{evidence_key}-forecasts.png"), full_page=True)


def run_case(browser, engine, name, width, height, theme):
    context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme, timezone_id="Asia/Tokyo", accept_downloads=True)
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
            backgrounds = page.locator('.workspace-launch-grid > a').evaluate_all("es=>es.map(e=>getComputedStyle(e).backgroundColor)")
            assert "rgb(255, 255, 255)" not in backgrounds, backgrounds
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
        evidence_key = f"{engine}-{name}-{theme}" if engine == "chromium" and name in ("phone", "desktop") else None
        capture_workflows(page, evidence_key)
        reports_and_company(page, evidence_key)
        pursuit_rooms_and_audit(page, evidence_key)
        sam_award_pages(page, evidence_key)
        if name in ("phone", "desktop"):
            proposal_editing(page, evidence_key)
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
