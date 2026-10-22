#!/usr/bin/env python3
"""Browser -> real Django -> PostgreSQL persistence checks in disposable CI.

No browser API interception. External government data comes from the isolated
provider fixture, and no live AI or payment provider is invoked.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from experience_qa_fixtures import EMAIL, NOTICE, PASSWORD

BASE = os.getenv("FORGEGOV_QA_BASE_URL", "http://127.0.0.1:3100").rstrip("/")
if BASE != "http://127.0.0.1:3100" or os.getenv("FORGEGOV_ISOLATED_QA") != "1":
    raise SystemExit("Full-stack mutations are restricted to explicit loopback QA.")
OUT = Path("artifacts/fullstack-qa")
OUT.mkdir(parents=True, exist_ok=True)


def run(page):
    page.goto(BASE + "/sign-in")
    page.get_by_label("Email", exact=True).fill(EMAIL)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Sign in securely", exact=True).click()
    page.wait_for_url(BASE + "/", timeout=30000)
    page.goto(BASE + "/capture/tasks")
    page.get_by_label("Task title", exact=True).fill("Full-stack QA task")
    page.get_by_label("Due date (your local time)", exact=True).fill("2026-11-02T09:00")
    page.get_by_role("button", name="Add task", exact=True).click()
    complete = page.get_by_role("button", name="Complete: Full-stack QA task", exact=True)
    complete.click()
    completed = page.get_by_role("button", name="Mark incomplete: Full-stack QA task", exact=True)
    expect(completed).to_have_attribute("aria-pressed", "true")
    page.reload()
    expect(completed).to_have_attribute("aria-pressed", "true")
    page.screenshot(path=str(OUT / "tasks.png"), full_page=True)

    page.goto(BASE + "/project-rooms")
    page.get_by_label("Room name", exact=True).fill("Full-stack QA room")
    page.get_by_role("button", name="Create Project Room", exact=True).click()
    room = page.get_by_role("link", name="Full-stack QA room", exact=True)
    expect(room).to_be_visible()
    page.reload()
    expect(room).to_be_visible()
    page.screenshot(path=str(OUT / "rooms.png"), full_page=True)
    room.click()
    page.get_by_role("heading", name="Full-stack QA room", exact=True).wait_for()
    page.get_by_role("button", name="Work & files", exact=True).click()
    page.get_by_placeholder("Add a task", exact=True).fill("Full-stack room task")
    page.get_by_role("button", name="Add task", exact=True).click()
    room_task = page.locator(".source-card").filter(has=page.get_by_text("Full-stack room task", exact=True))
    room_task.locator("select").select_option("done")
    expect(room_task.locator("select")).to_be_enabled()
    expect(room_task.locator("select")).to_have_value("done")
    page.reload()
    page.get_by_role("button", name="Work & files", exact=True).click()
    expect(room_task.locator("select")).to_have_value("done")
    page.screenshot(path=str(OUT / "room-work.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 2
    page.screenshot(path=str(OUT / "room-work-phone.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})

    page.goto(BASE + f"/opportunities/federal-contracts/{NOTICE}")
    page.get_by_role("tab", name="Proposal", exact=True).click()
    editor = page.get_by_label("Section content", exact=True)
    expect(editor).to_be_visible(timeout=30000)
    editor.fill("Full-stack QA revision")
    page.get_by_role("button", name="Save section", exact=True).click()
    page.get_by_role("status").filter(has_text="Section saved and revision recorded.").wait_for()
    page.reload()
    page.get_by_role("tab", name="Proposal", exact=True).click()
    expect(editor).to_have_value("Full-stack QA revision", timeout=30000)
    page.screenshot(path=str(OUT / "proposal.png"), full_page=True)

    page.get_by_role("tab", name="Pricing", exact=True).click()
    page.get_by_role("heading", name="Pricing Workspace", exact=True).wait_for()
    page.get_by_role("button", name="Cost Build-Up", exact=True).click()
    page.locator(".pricing-form").get_by_label("Name", exact=True).fill("Full-stack QA labor")
    page.get_by_label("Hours", exact=True).fill("2")
    page.get_by_label("Hourly Cost", exact=True).fill("50")
    page.get_by_role("button", name="Add Cost Item", exact=True).click()
    expect(page.get_by_text("Full-stack QA labor", exact=True)).to_be_visible()
    page.reload()
    page.get_by_role("tab", name="Pricing", exact=True).click()
    page.get_by_role("button", name="Cost Build-Up", exact=True).click()
    expect(page.get_by_text("Full-stack QA labor", exact=True)).to_be_visible()
    page.screenshot(path=str(OUT / "pricing-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "pricing-phone.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 2


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tokyo")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        run(page)
        assert not errors, errors
        (OUT / "report.json").write_text(json.dumps({"passed": True, "checks": ["task completion reload", "room creation reload", "room task completion reload", "proposal revision reload", "pricing item reload", "room and pricing phone overflow"], "page_errors": errors}, indent=2))
    except Exception as error:
        page.screenshot(path=str(OUT / "failure.png"), full_page=True)
        (OUT / "report.json").write_text(json.dumps({"passed": False, "error": str(error), "page_errors": errors}, indent=2))
        raise
    finally:
        browser.close()
