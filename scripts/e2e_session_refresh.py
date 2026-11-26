#!/usr/bin/env python3
"""Exercise expired access cookies against real isolated Django sessions in two tabs."""
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright, expect

from experience_qa_fixtures import EMAIL, PASSWORD

BASE = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3100").rstrip("/")
if BASE != "http://127.0.0.1:3100" or os.getenv("FORGEGOV_ISOLATED_QA") != "1":
    raise SystemExit("Session regression is restricted to explicit loopback QA.")
OUT = Path("artifacts/fullstack-qa")
OUT.mkdir(parents=True, exist_ok=True)


async def check_engine(playwright, engine):
    browser = await getattr(playwright, engine).launch()
    context = await browser.new_context(viewport={"width": 1440, "height": 900})
    first = await context.new_page()
    second = await context.new_page()
    errors = []
    for page in (first, second):
        page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        await first.goto(BASE + "/sign-in")
        await first.get_by_label("Email", exact=True).fill(EMAIL)
        await first.get_by_label("Password", exact=True).fill(PASSWORD)
        await first.get_by_role("button", name="Sign in securely", exact=True).click()
        await first.wait_for_url(BASE + "/", timeout=30000)
        await expect(first.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
        await first.wait_for_load_state("networkidle")
        # Follow the visible SPA navigation after login. A hard goto while
        # Next finishes the redirect can cancel WebKit's active navigation.
        await first.get_by_role("link", name="Pipelines", exact=True).click()
        await first.wait_for_url(BASE + "/capture/pipelines")
        await first.wait_for_load_state("networkidle")
        await second.goto(BASE + "/capture/tasks", wait_until="networkidle")
        for cycle in range(3):
            await asyncio.gather(*[page.wait_for_load_state("networkidle") for page in (first, second)])
            # Only synthetic, disposable CI cookies are modified. The real
            # HttpOnly refresh cookie must recover both tabs after access expiry.
            await context.clear_cookies(name="forgegov_access")
            await asyncio.gather(
                first.reload(wait_until="networkidle"),
                second.reload(wait_until="networkidle"),
            )
            for page, path in ((first, "/capture/pipelines"), (second, "/capture/tasks")):
                await expect(page.get_by_role("button", name="Sign out", exact=True)).to_be_visible(timeout=15000)
                assert page.url == BASE + path, (engine, cycle, page.url)
        # A temporary session-check outage should preserve the requested page.
        async def unavailable(route):
            await route.fulfill(status=503, json={"detail": "Temporarily unavailable"})

        session_route = "**/api/auth/me/"
        await first.route(session_route, unavailable)
        await first.reload()
        await expect(first.get_by_role("heading", name="Unable to verify your session")).to_be_visible()
        assert first.url == BASE + "/capture/pipelines"
        await first.unroute(session_route, unavailable)
        await first.get_by_role("button", name="Try again", exact=True).click()
        await expect(first.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
        assert first.url == BASE + "/capture/pipelines"
        assert not errors, errors
        print("PASS session expiry recovery", engine, "two tabs, three cycles", flush=True)
        return {"engine": engine, "passed": True, "tabs": 2, "expiry_cycles": 3}
    except Exception:
        await first.screenshot(path=str(OUT / f"{engine}-session-refresh-failure.png"), full_page=True)
        raise
    finally:
        await context.close()
        await browser.close()


async def main():
    results = []
    async with async_playwright() as playwright:
        for engine in ("chromium", "firefox", "webkit"):
            results.append(await check_engine(playwright, engine))
    (OUT / "session-refresh-report.json").write_text(json.dumps({"passed": True, "cases": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
