#!/usr/bin/env python3
"""Controlled connection failures must not masquerade as expired sessions."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from visual_qa_subcontracting import install_api_fixtures
from visual_qa_billing import SESSION

BASE = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3100").rstrip("/")
OUT = Path("artifacts/visual-qa/session-verification")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    results = []
    with sync_playwright() as p:
        for engine in ("chromium", "firefox", "webkit"):
            browser = getattr(p, engine).launch()
            try:
                for failure in ("network", "unavailable", "unauthorized"):
                    context = browser.new_context(viewport={"width": 390, "height": 844})
                    page = context.new_page()
                    install_api_fixtures(page)
                    state = {"recover": False}
                    def session(route):
                        if state["recover"]:
                            route.fulfill(status=200, content_type="application/json", body=json.dumps(SESSION))
                        elif failure == "network":
                            route.abort("failed")
                        else:
                            route.fulfill(status=401 if failure == "unauthorized" else 503, content_type="application/json", body=json.dumps({"detail": "Controlled verification failure"}))
                    page.route("**/api/auth/me/", session)
                    page.route("**/api/auth/refresh/", lambda r: r.fulfill(status=401, content_type="application/json", body='{"detail":"Controlled expired session"}'))
                    page.goto(BASE + "/capture/tasks", wait_until="commit")
                    if failure == "unauthorized":
                        page.wait_for_url("**/sign-in?next=**")
                        expect(page.get_by_role("heading", name="Sign in to ForgeGov", exact=True)).to_be_visible()
                    else:
                        expect(page.get_by_role("heading", name="Workspace verification interrupted", exact=True)).to_be_visible()
                        assert page.url == BASE + "/capture/tasks", page.url
                        assert not page.get_by_role("button", name="Sign out", exact=True).is_visible()
                        assert not page.locator("#workspace-navigation").count(), "private shell rendered without verification"
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
                        page.screenshot(path=str(OUT / f"{engine}-{failure}.png"), full_page=True)
                        state["recover"] = True
                        page.get_by_role("button", name="Retry verification", exact=True).click()
                        expect(page.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
                        assert page.url == BASE + "/capture/tasks", page.url
                    results.append({"engine": engine, "failure": failure, "passed": True})
                    print("PASS session verification", engine, failure, flush=True)
                    context.close()
            finally:
                browser.close()
    (OUT / "report.json").write_text(json.dumps({"passed": True, "cases": results}, indent=2))


if __name__ == "__main__":
    main()
