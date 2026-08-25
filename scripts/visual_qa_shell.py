#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright
from visual_qa_subcontracting import install_api_fixtures

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
OUT = Path(os.getenv("FORGEGOV_QA_ARTIFACT_DIR", str(ROOT / "artifacts" / "visual-qa")))
OUT.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    ("phone", 390, 844),
    ("tablet-portrait", 768, 1024),
    ("tablet-landscape", 1024, 768),
    ("laptop", 1280, 800),
    ("desktop", 1440, 900),
]

def visible(locator) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False

def run_case(browser, name: str, width: int, height: int) -> list[str]:
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    install_api_fixtures(page)
    issues: list[str] = []
    try:
        page.goto(BASE_URL + "/opportunities/subcontracting", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".forge-shell", timeout=15000)
        page.wait_for_timeout(450)

        metrics = page.evaluate("() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,body:(document.body?.innerText||'').trim().length})")
        if metrics["body"] < 20:
            issues.append("main page became blank or near-blank")
        if metrics["sw"] > metrics["cw"] + 2:
            issues.append(f"horizontal overflow {metrics['sw']}px > {metrics['cw']}px")

        if width > 900:
            if visible(page.locator(".shell-backdrop")):
                issues.append("mobile shell backdrop is visible above 900px")
            if visible(page.locator('button[aria-label="Open navigation"]')):
                issues.append("mobile navigation opener is visible above 900px")

            toggle = page.locator(".desktop-sidebar-toggle")
            if not visible(toggle):
                issues.append("desktop sidebar toggle is not visible")
            else:
                before = "sidebar-collapsed" in (page.locator(".forge-shell").get_attribute("class") or "")
                toggle.click()
                page.wait_for_timeout(180)
                after = "sidebar-collapsed" in (page.locator(".forge-shell").get_attribute("class") or "")
                if before == after:
                    issues.append("desktop sidebar toggle did not change sidebar state")

                if not after:
                    toggle.click()
                    page.wait_for_timeout(160)
                    after = "sidebar-collapsed" in (page.locator(".forge-shell").get_attribute("class") or "")
                if after:
                    labels = page.locator(".forge-sidebar .forge-nav-label")
                    for i in range(min(labels.count(), 8)):
                        if labels.nth(i).is_visible():
                            issues.append("collapsed icon rail still exposes navigation label text")
                            break
                    group = page.locator(".forge-nav-group > button").first
                    if visible(group):
                        group.click()
                        page.wait_for_timeout(220)
                        still_collapsed = "sidebar-collapsed" in (page.locator(".forge-shell").get_attribute("class") or "")
                        if still_collapsed:
                            issues.append("collapsed group button did not expand the sidebar")
        else:
            opener = page.locator('button[aria-label="Open navigation"]')
            if not visible(opener):
                issues.append("mobile navigation opener is not visible")
            else:
                opener.first.click()
                page.wait_for_timeout(180)
                sidebar = page.locator(".forge-sidebar")
                if "open" not in (sidebar.get_attribute("class") or ""):
                    issues.append("mobile drawer did not open")
                close = page.locator(".forge-sidebar .mobile-only")
                if visible(close):
                    close.first.click()
                    page.wait_for_timeout(180)
                    if "open" in (sidebar.get_attribute("class") or ""):
                        issues.append("mobile drawer did not close")
                body_len = page.evaluate("() => (document.body?.innerText || '').trim().length")
                if body_len < 20:
                    issues.append("page became blank after mobile drawer interaction")
    finally:
        context.close()
    return sorted(set(issues))

def main() -> int:
    report = {"release": "3.2.1.3", "base_url": BASE_URL, "cases": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for name, width, height in SCENARIOS:
                issues = run_case(browser, name, width, height)
                report["cases"][name] = issues
                print(f"[{'PASS' if not issues else 'FAIL'}] {name:16s} {width}x{height}")
                for issue in issues:
                    print(f"       - {issue}")
        finally:
            browser.close()

    failures = {k: v for k, v in report["cases"].items() if v}
    report["passed"] = not failures
    report["failed_cases"] = len(failures)
    path = OUT / "shell-workflow-report.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nShell UX report: {path}")
    if failures:
        print(f"FAILED: {len(failures)} breakpoint scenarios.")
        return 1
    print(f"PASSED: {len(report['cases'])} interactive breakpoint scenarios.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
