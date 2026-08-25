#!/usr/bin/env python3
"""Deterministic cross-browser responsive QA for ForgeGov Subcontracting.

Runs the real Next.js pages against Playwright-intercepted API fixtures so the UI can
be stress-tested without touching production data or requiring a privileged account.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import BrowserType, Page, Route, sync_playwright
except ImportError:
    print("Playwright is not installed. Run ./scripts/setup_visual_qa.sh first.", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", str(ROOT / "artifacts" / "visual-qa")))
OUT.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    ("phone-390", 390, 844),
    ("phone-430", 430, 932),
    ("tablet-portrait", 768, 1024),
    ("tablet-landscape", 1024, 768),
    ("laptop-1280", 1280, 800),
    ("desktop-1440", 1440, 900),
    ("desktop-1920", 1920, 1080),
    # CSS viewport equivalents of a 1280px laptop at browser zoom.
    ("laptop-125pct-zoom-equivalent", 1024, 640),
    ("laptop-150pct-zoom-equivalent", 854, 534),
]

LONG_TITLE = (
    "Integrated installation, field maintenance, logistics support, engineering change implementation, "
    "and sustainment services for tactical vehicle mission systems across multiple CONUS locations"
)
LONG_PRIME = "National Mission Systems Engineering, Sustainment, Logistics and Technical Services Corporation"
LONG_DESCRIPTION = (
    "The prime contractor is seeking qualified small-business subcontractors capable of providing field-level technical "
    "support, preventive and corrective maintenance, parts logistics, configuration documentation, technician training, "
    "and surge support. Performance may require simultaneous support at geographically separated facilities with short "
    "response windows and detailed monthly reporting requirements."
)

SUBNET_ROWS = [
    {
        "source_id": f"qa-subnet-{index:03d}",
        "title": LONG_TITLE if index == 1 else f"Regional subcontract opportunity {index}: {LONG_TITLE[:90]}",
        "description": LONG_DESCRIPTION,
        "prime_contractor": LONG_PRIME,
        "place_of_performance": "San Antonio, Texas / Fort Cavazos, Texas / multiple CONUS locations",
        "naics": "811310",
        "closing_date": "2026-09-30T17:00:00Z",
        "performance_start_date": "2026-11-01",
        "contact": "Alexandra Capture Manager, alexandra.capture@example-prime.test, +1 555 010 4242",
        "source_url": "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
    }
    for index in range(1, 7)
]

SUBAWARDS = [
    {
        "subcontractor": "Advanced Field Logistics and Sustainment Solutions, LLC",
        "prime_contractor": LONG_PRIME,
        "description": LONG_DESCRIPTION,
        "amount": 4850000 + i * 325000,
        "piid": f"W56HZV26D{i:04d}",
    }
    for i in range(1, 6)
]

WORKSPACE = {
    "opportunity": {
        "source_id": "qa-subnet-001",
        "source": "sba_subnet",
        "title": LONG_TITLE,
        "description": LONG_DESCRIPTION * 2,
        "prime_contractor": LONG_PRIME,
        "solicitation_number": "HD-QA-2026-SUBCONTRACT-000001-LONG-REFERENCE",
        "naics": "811310",
        "psc": "J023",
        "closing_date": "2026-09-30T17:00:00Z",
        "performance_start": "2026-11-01",
        "place_of_performance": "San Antonio, Texas / Fort Cavazos, Texas / multiple CONUS locations",
        "source_url": "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
        "active": True,
        "notice_type": "subcontract_opportunity",
        "source_metadata": {
            "source_name": "SBA SUBNet",
            "observed_at": "2026-08-24T08:00:00Z",
            "classification": "public_source",
        },
    },
    "contact": {
        "name": "Alexandra Capture Manager",
        "email": "alexandra.capture@example-prime.test",
        "phone": "+1 555 010 4242",
        "raw": "Alexandra Capture Manager | alexandra.capture@example-prime.test | +1 555 010 4242",
    },
    "prime": {
        "name": LONG_PRIME,
        "vendor": {
            "id": 42,
            "name": LONG_PRIME,
            "uei": "QA1234567890",
            "cage_code": "QATEST",
            "website": "https://example-prime.test",
            "city": "Arlington",
            "state": "VA",
            "naics_codes": ["541330", "811310"],
            "socioeconomic_statuses": [],
        },
        "award_summary": {
            "award_count": 38,
            "obligated_amount": 147500000,
            "potential_amount": 312000000,
            "classification": "public_award_history",
            "top_agencies": [
                {"awarding_agency": "Department of the Army", "awards": 17, "obligated": 85000000},
                {"awarding_agency": "Department of the Air Force", "awards": 11, "obligated": 42000000},
                {"awarding_agency": "Defense Logistics Agency", "awards": 10, "obligated": 20500000},
            ],
        },
        "recent_awards": [
            {
                "id": i,
                "award_id": f"QA-AWARD-{i}",
                "award_number": f"W56HZV26C{i:04d}",
                "awarding_agency": "Department of the Army",
                "naics_code": "541330",
                "psc_code": "J023",
                "obligated_amount": 8250000 + i * 100000,
                "potential_amount": 14000000,
                "start_date": "2025-10-01",
                "end_date": "2028-09-30",
            }
            for i in range(1, 5)
        ],
    },
    "parent_contract_candidates": [
        {
            "award_id": f"PARENT-QA-{i}",
            "award_number": f"W56HZV24D{i:04d}",
            "awarding_agency": "Department of the Army",
            "naics_code": "541330",
            "psc_code": "J023",
            "obligated_amount": 22000000 + i * 1000000,
            "potential_amount": 98000000,
            "start_date": "2024-10-01",
            "end_date": "2029-09-30",
            "match_reason": "Prime contractor, NAICS, agency, and performance-window evidence overlap with the listing.",
            "classification": "possible_parent_contract",
        }
        for i in range(1, 4)
    ],
    "pipeline": {
        "active": True,
        "id": 901,
        "stage": "reviewing",
        "owner": "QA Capture Manager With A Long Display Name",
        "next_action": "Validate labor categories, geographic coverage, and prime flow-down requirements before bid/no-bid review.",
        "probability_of_win": 45,
    },
    "capture_links": {
        "company_profile": "/participants/vendors/profile?name=qa",
        "pipeline": "/capture/pipelines",
        "project_rooms": "/project-rooms",
    },
    "warnings": ["Parent-contract candidates are evidence signals and are not asserted as confirmed relationships."],
}

SESSION = {
    "user": {"id": 999001, "email": "visual.qa@forgegov.test", "first_name": "Visual", "last_name": "QA"},
    "organization": {"id": 999001, "name": "ForgeGov Visual QA Organization With Long Name", "slug": "forgegov-visual-qa"},
    "role": "owner",
    "capabilities": {
        "company_admin": True,
        "financial_read": True,
        "financial_write": True,
        "proposal_read": True,
        "proposal_write": True,
        "submission_control": True,
        "executive_financial": True,
        "project_room_manage": True,
    },
}


def api_payload(path: str):
    if path == "/api/auth/me/":
        return SESSION
    if path == "/api/auth/workspaces/":
        return {"workspaces": [{"organization": SESSION["organization"], "role": "owner", "job_title": "Visual QA"}]}
    if path == "/api/platform-admin/me/":
        return {"platform_admin": False}
    if path == "/api/alerts/":
        return {"results": []}
    if path == "/api/collaboration/notifications/":
        return {"results": []}
    if path == "/api/auth/invitations/pending/":
        return []
    if path == "/api/integrations/microsoft/status/":
        return {
            "configured": True,
            "connected": True,
            "verified": True,
            "verified_at": "2026-08-24T08:00:00Z",
            "status": "connected",
            "account_email": "visual.qa@example.test",
            "default_team_name": "Capture Team With A Long Name",
            "default_channel_name": "Subcontract Opportunities",
        }
    if path == "/api/live/sba/subnet/":
        return {
            "results": SUBNET_ROWS,
            "has_next": True,
            "page": 0,
            "total_records": 128,
            "status": "live",
            "source_name": "SBA SUBNet",
        }
    if path.startswith("/api/live/sba/subnet/"):
        return WORKSPACE
    if path == "/api/live/sam/subawards/":
        return {"results": SUBAWARDS}
    if path.startswith("/api/intelligence/search/"):
        return {"results": []}
    return {"results": []}


def install_api_fixtures(page: Page) -> None:
    origin = BASE_URL

    def handler(route: Route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        if "/api/" not in parsed.path:
            route.continue_()
            return
        if request.method == "OPTIONS":
            route.fulfill(
                status=204,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Headers": "Content-Type,X-CSRFToken",
                    "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
                },
                body="",
            )
            return
        body = api_payload(parsed.path)
        route.fulfill(
            status=200,
            content_type="application/json",
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            },
            body=json.dumps(body),
        )

    page.route("**/api/**", handler)


def layout_issues(page: Page, root_selector: str) -> list[str]:
    return page.eval_on_selector(
        root_selector,
        """(root) => {
          const issues = [];
          const html = document.documentElement;
          if (html.scrollWidth > html.clientWidth + 2) {
            issues.push(`page horizontal overflow: ${html.scrollWidth}px > ${html.clientWidth}px`);
          }
          const visible = (el) => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 0 && r.height > 0;
          };
          root.querySelectorAll('[data-qa-no-x-overflow="true"]').forEach((el) => {
            if (el.scrollWidth > el.clientWidth + 2) {
              issues.push(`${el.getAttribute('data-qa') || el.className || el.tagName} internal horizontal overflow: ${el.scrollWidth}px > ${el.clientWidth}px`);
            }
          });
          root.querySelectorAll('[data-qa], .primary-button, .secondary-button, .icon-button, input, select, textarea').forEach((el) => {
            if (!visible(el)) return;
            const r = el.getBoundingClientRect();
            if (r.left < -2 || r.right > window.innerWidth + 2) {
              issues.push(`${el.getAttribute('data-qa') || el.className || el.tagName} escapes viewport horizontally (${Math.round(r.left)}..${Math.round(r.right)} / ${window.innerWidth})`);
            }
          });
          root.querySelectorAll('button, a.primary-button, a.secondary-button, a.icon-button').forEach((el) => {
            if (!visible(el)) return;
            const r = el.getBoundingClientRect();
            if (r.height < 34 || r.width < 34) {
              issues.push(`undersized interactive control: ${el.textContent?.trim().slice(0,60) || el.getAttribute('aria-label') || el.className} (${Math.round(r.width)}x${Math.round(r.height)})`);
            }
          });
          return [...new Set(issues)];
        }""",
    )


def _wait_for_qa_root(page: Page, selector: str, label: str) -> None:
    try:
        page.wait_for_selector(selector, timeout=30000)
    except Exception as exc:
        auth_loading = page.locator('.auth-loading').count() > 0
        body = page.locator('body').inner_text(timeout=5000)[:500].replace('\n', ' ')
        if auth_loading:
            raise RuntimeError(
                f"{label} never hydrated past ForgeGov auth loading at {page.url}; "
                f"body={body!r}"
            ) from exc
        raise RuntimeError(
            f"{label} root {selector} was not rendered at {page.url}; body={body!r}"
        ) from exc


def check_index(page: Page, browser_name: str, scenario: str) -> list[str]:
    page.goto(f"{BASE_URL}/opportunities/subcontracting", wait_until="domcontentloaded", timeout=45000)
    _wait_for_qa_root(page, '[data-qa="subcontracting-index"]', 'subcontracting index')
    page.wait_for_selector('[data-qa="subcontract-opportunity-card"]', timeout=30000)
    page.wait_for_timeout(250)
    issues = layout_issues(page, '[data-qa="subcontracting-index"]')
    page.screenshot(path=str(OUT / f"{browser_name}-{scenario}-subcontracting.png"), full_page=True)
    page.get_by_role("tab", name="SAM subawards").click()
    page.wait_for_selector('[data-qa="subcontract-subaward-feed"]')
    page.wait_for_timeout(100)
    issues.extend(layout_issues(page, '[data-qa="subcontracting-index"]'))
    return sorted(set(issues))


def check_workspace(page: Page, browser_name: str, scenario: str) -> list[str]:
    page.goto(f"{BASE_URL}/opportunities/subcontracting/qa-subnet-001", wait_until="domcontentloaded", timeout=45000)
    _wait_for_qa_root(page, '[data-qa="subcontract-workspace"]', 'subcontract workspace')
    page.wait_for_selector('[data-qa="subcontract-command-grid"]', timeout=30000)
    page.wait_for_timeout(250)
    issues = layout_issues(page, '[data-qa="subcontract-workspace"]')
    page.screenshot(path=str(OUT / f"{browser_name}-{scenario}-workspace-overview.png"), full_page=True)
    for tab in ("Prime & parent contract", "Capture intelligence", "Collaboration"):
        page.get_by_role("button", name=tab).click()
        page.wait_for_timeout(120)
        issues.extend(layout_issues(page, '[data-qa="subcontract-workspace"]'))
    page.screenshot(path=str(OUT / f"{browser_name}-{scenario}-workspace-collaboration.png"), full_page=True)
    return sorted(set(issues))


def run_browser(browser_type: BrowserType, browser_name: str, report: dict) -> None:
    browser = browser_type.launch(headless=True)
    try:
        for scenario, width, height in SCENARIOS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            install_api_fixtures(page)
            case = {"viewport": {"width": width, "height": height}, "issues": []}
            try:
                case["issues"].extend(check_index(page, browser_name, scenario))
                case["issues"].extend(check_workspace(page, browser_name, scenario))
                case["issues"] = sorted(set(case["issues"]))
            except Exception as exc:  # keep the whole matrix running and report the failing case
                case["issues"].append(f"test execution error: {type(exc).__name__}: {exc}")
            finally:
                context.close()
            report["cases"][f"{browser_name}:{scenario}"] = case
            status = "PASS" if not case["issues"] else "FAIL"
            print(f"[{status}] {browser_name:8s} {scenario:30s} {width}x{height}")
            for issue in case["issues"]:
                print(f"       - {issue}")
    finally:
        browser.close()


def main() -> int:
    report = {
        "release": "3.2.1.3",
        "base_url": BASE_URL,
        "matrix": [name for name, _, _ in SCENARIOS],
        "cases": {},
    }
    with sync_playwright() as p:
        selected = [name.strip() for name in os.getenv("FORGEGOV_QA_BROWSERS", "chromium,firefox,webkit").split(",") if name.strip()]
        available = {"chromium": p.chromium, "firefox": p.firefox, "webkit": p.webkit}
        for browser_name in selected:
            if browser_name not in available:
                raise SystemExit(f"Unsupported browser: {browser_name}")
            run_browser(available[browser_name], browser_name, report)

    failures = {name: case for name, case in report["cases"].items() if case["issues"]}
    report["passed"] = not failures
    report["failed_cases"] = len(failures)
    report_path = OUT / "subcontracting-responsive-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nVisual QA report: {report_path}")
    if failures:
        print(f"FAILED: {len(failures)} responsive/browser cases failed visual QA (layout or test execution).")
        return 1
    print(f"PASSED: {len(report['cases'])} browser/viewport cases; no horizontal overflow or undersized controls detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
