"""Read-only public production checks with synthetic invalid-login credentials."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

WEB = "https://forge-gov.com"
API = "https://api.forge-gov.com/api"
OUT = Path("artifacts/production-smoke")
OUT.mkdir(parents=True, exist_ok=True)
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(url, payload=None, headers=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers={"Cache-Control": "no-cache", **(headers or {})})
    try:
        response = client.open(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read(), response.headers


for attempt in range(48):
    try:
        code, raw, _ = request(API + "/ready/")
        readiness = json.loads(raw)
        if code == 200 and readiness.get("status") == "ready" and readiness.get("version") == "3.3.5":
            break
        print("Waiting for release readiness", code, readiness.get("version"), flush=True)
    except (OSError, ValueError) as error:
        print("Waiting for readiness", type(error).__name__, flush=True)
    time.sleep(10)
else:
    raise AssertionError("Production v3.3.5 readiness did not become healthy.")

report = {"readiness": readiness, "pages": [], "browser_cases": []}
for path in ("/", "/sign-in", "/register", "/request-access", "/support", "/terms", "/privacy"):
    code, body, headers = request(WEB + path)
    assert code == 200, (path, code)
    assert b"<html" in body and b"<title" in body, path
    assert headers.get("X-Content-Type-Options") == "nosniff", path
    report["pages"].append({"path": path, "status": code})
for asset in ("discovery", "market", "capture", "rooms", "forgeai"):
    code, body, headers = request(WEB + "/product/" + asset + ".webp")
    assert code == 200 and headers.get_content_type().startswith("image/") and len(body) > 1000, asset

code, _, _ = request(API + "/dashboard/summary/")
assert code == 401, code
code, csrf_body, _ = request(API + "/auth/csrf/")
assert code == 200
csrf = json.loads(csrf_body)["csrfToken"]
code, body, headers = request(
    API + "/auth/login/",
    {"email": "release-v335-smoke@example.invalid", "password": "synthetic-invalid-release-password"},
    {"Origin": WEB, "Referer": WEB + "/sign-in", "Content-Type": "application/json", "X-CSRFToken": csrf},
)
assert code == 401 and json.loads(body).get("detail") == "Email or password is incorrect.", (code, body[:200])
assert headers.get("Access-Control-Allow-Origin") == WEB
report["authentication_guards"] = "protected read and invalid login return 401"

with sync_playwright() as playwright:
    for engine in ("chromium", "firefox", "webkit"):
        browser = getattr(playwright, engine).launch()
        for width, height in ((390, 844), (768, 1024), (1440, 1000)):
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            errors = []
            private_requests = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda req: private_requests.append(req.url) if any(
                endpoint in req.url for endpoint in ("/alerts/", "/collaboration/notifications/", "/auth/invitations/pending/")
            ) else None)
            page.goto(WEB, wait_until="networkidle", timeout=60000)
            expect(page.get_by_role("heading", level=1)).to_contain_text("Find the opportunity.")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (engine, width)
            for tab in ("Discover", "Qualify", "Capture", "Project Rooms", "ForgeAI"):
                page.get_by_role("tab", name=tab, exact=True).click()
                expect(page.get_by_role("tab", name=tab, exact=True)).to_have_attribute("aria-selected", "true")
                expect(page.locator("#tour-panel img")).to_be_visible()
                page.wait_for_function("document.querySelector('#tour-panel img').complete && document.querySelector('#tour-panel img').naturalWidth > 0")
            for img in page.locator("main img:visible").all():
                img.scroll_into_view_if_needed()
                expect(img).to_be_visible()
                img.evaluate("(image) => image.complete ? Promise.resolve() : new Promise((resolve, reject) => {image.addEventListener('load', resolve, {once:true}); image.addEventListener('error', reject, {once:true});})")
                assert img.evaluate("image => image.naturalWidth > 0")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(OUT / f"{engine}-{width}-homepage.png"), full_page=True)
            for path in ("/sign-in", "/register", "/support"):
                page.goto(WEB + path, wait_until="networkidle", timeout=60000)
                expect(page.get_by_role("heading", level=1).first).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (engine, width, path)
            assert not errors, errors
            assert not private_requests, private_requests
            report["browser_cases"].append({"engine": engine, "width": width, "passed": True})
            print("PASS live production", engine, width, flush=True)
            context.close()
        browser.close()
(OUT / "report.json").write_text(json.dumps(report, indent=2))
print("Production smoke passed", json.dumps(report), flush=True)
