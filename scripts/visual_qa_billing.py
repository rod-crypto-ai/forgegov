#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import Page, Route, sync_playwright
except ImportError:
    print(
        "Playwright is not installed. Run ./scripts/setup_visual_qa.sh first.",
        file=sys.stderr,
    )
    raise SystemExit(2)


BASE_URL = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", "artifacts/visual-qa"))
OUT.mkdir(parents=True, exist_ok=True)
SCENARIOS = [
    ("phone-390", 390, 844),
    ("phone-430", 430, 932),
    ("tablet-portrait", 768, 1024),
    ("tablet-landscape", 1024, 768),
    ("laptop-1280", 1280, 800),
    ("desktop-1440", 1440, 900),
    ("desktop-1920", 1920, 1080),
]
SESSION = {
    "user": {
        "id": 9901,
        "email": "billing.qa@forgegov.test",
        "first_name": "Billing",
        "last_name": "QA",
    },
    "organization": {
        "id": 9901,
        "name": "Long Mission Support & Federal Logistics Solutions, LLC",
        "slug": "billing-qa",
    },
    "role": "owner",
    "capabilities": {"billing_admin": True, "company_admin": True},
}
SUMMARY = {
    "organization": SESSION["organization"],
    "subscription": {
        "status": "legacy",
        "access_state": "legacy",
        "permits_access": True,
        "provider": "stripe",
        "grandfathered": False,
        "grandfathered_at": None,
        "grandfathered_reason": "",
        "seat_quantity": 4,
        "trial_available": True,
        "trial_ends_at": None,
        "current_period_starts_at": None,
        "current_period_ends_at": None,
        "grace_ends_at": None,
        "cancel_at_period_end": False,
    },
    "plan": {
        "code": "professional-annual",
        "name": "ForgeGov Professional",
        "description": "Annual government-contracting intelligence, capture, collaboration, proposal, and ForgeAI workspace access.",
        "currency": "USD",
        "price_cents": 200000,
        "billing_interval": "year",
        "entitlements": {"platform": True},
        "limits": {},
    },
    "offer": {
        "code": "professional-annual",
        "name": "ForgeGov Professional",
        "description": "Annual ForgeGov platform access.",
        "currency": "USD",
        "price_cents": 200000,
        "billing_interval": "year",
        "trial_days": 30,
    },
    "usage": [
        {
            "metric": "forgeai_runs",
            "quantity": 18,
            "limit": None,
            "period_starts_at": "2026-10-01T00:00:00Z",
            "period_ends_at": "2026-11-01T00:00:00Z",
        }
    ],
    "billing": {
        "provider": "stripe",
        "checkout_enabled": True,
        "portal_enabled": True,
        "checkout_available": True,
        "portal_available": False,
        "detail": "Automated billing is configured.",
    },
}


def install_fixtures(page: Page, session=None, summary=None) -> None:
    session = SESSION if session is None else session
    summary = SUMMARY if summary is None else summary
    def handler(route: Route) -> None:
        path = urlparse(route.request.url).path
        if "/api/" not in path:
            route.continue_()
            return
        payload: object = {"results": []}
        if path == "/api/auth/me/":
            payload = session
        elif path == "/api/auth/workspaces/":
            payload = {
                "workspaces": [
                    {"organization": SESSION["organization"], "role": "owner"}
                ]
            }
        elif path == "/api/platform-admin/me/":
            payload = {"platform_admin": False}
        elif path == "/api/billing/summary/":
            payload = summary
        elif path == "/api/auth/csrf/":
            payload = {"csrfToken": "billing-qa"}
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps(payload)
        )

    page.route("**/api/**", handler)


def run_case(
    browser_type, browser_name: str, scenario: tuple[str, int, int]
) -> list[str]:
    name, width, height = scenario
    browser = browser_type.launch(headless=True)
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    install_fixtures(page)
    issues: list[str] = []
    try:
        page.goto(f"{BASE_URL}/billing", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector('[data-qa="billing-page"]', timeout=15000)
        page.get_by_role("heading", name="Plan & billing").wait_for(timeout=15000)
        page.get_by_role("button", name="Start 30-day trial").wait_for(timeout=15000)
        page.keyboard.press("Tab")
        metrics = page.evaluate("""() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyLength: (document.body?.innerText || '').trim().length,
            tinyButtons: [...document.querySelectorAll('button,a')].filter((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && (rect.width < 32 || rect.height < 32);
            }).length,
        })""")
        if metrics["scrollWidth"] > metrics["clientWidth"] + 2:
            issues.append(
                f"horizontal overflow {metrics['scrollWidth']}px > {metrics['clientWidth']}px"
            )
        if metrics["bodyLength"] < 350:
            issues.append("billing page became blank or near-blank")
        if metrics["tinyButtons"]:
            issues.append(
                f"{metrics['tinyButtons']} visible controls smaller than 32px"
            )
        page.screenshot(
            path=str(OUT / f"v330-{browser_name}-{name}-billing.png"), full_page=True
        )
        # A fresh unpaid session must be sent to billing before product content mounts.
        unpaid_context = browser.new_context(viewport={"width": width, "height": height})
        unpaid_page = unpaid_context.new_page()
        install_fixtures(unpaid_page,
            session={**SESSION, "subscription": {"permits_access": False}},
            summary={**SUMMARY, "subscription": {**SUMMARY["subscription"], "permits_access": False}})
        unpaid_page.goto(f"{BASE_URL}/capture/tasks", wait_until="domcontentloaded")
        unpaid_page.wait_for_url(f"{BASE_URL}/billing", timeout=15000)
        unpaid_page.get_by_role("alert").filter(has_text="Subscription required").wait_for(timeout=15000)
        unpaid_page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        unpaid_page.wait_for_url(f"{BASE_URL}/billing", timeout=15000)
        unpaid_context.close()
    finally:
        context.close()
        browser.close()
    return issues


def main() -> int:
    report = {"release": "3.3.0", "base_url": BASE_URL, "cases": {}}
    with sync_playwright() as playwright:
        browsers = {
            "chromium": playwright.chromium,
            "firefox": playwright.firefox,
            "webkit": playwright.webkit,
        }
        for browser_name, browser_type in browsers.items():
            for scenario in SCENARIOS:
                key = f"{browser_name}:{scenario[0]}"
                try:
                    issues = run_case(browser_type, browser_name, scenario)
                except Exception as exc:  # noqa: BLE001 - retain every browser/viewport result
                    issues = [f"test execution error: {type(exc).__name__}: {exc}"]
                report["cases"][key] = issues
                print(
                    f"[{'PASS' if not issues else 'FAIL'}] {key}{f': {issues}' if issues else ''}"
                )
    failures = {key: value for key, value in report["cases"].items() if value}
    report["passed"] = not failures
    (OUT / "v330-billing-responsive-report.json").write_text(
        json.dumps(report, indent=2)
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
