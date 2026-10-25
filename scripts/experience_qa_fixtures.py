#!/usr/bin/env python3
"""Synthetic fixtures for the disposable Docker CI database only.

Government HTTP responses are controlled fixtures; application APIs and storage
remain real. This is not evidence of live provider availability.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EMAIL = "fullstack.qa@example.invalid"
PASSWORD = "Disposable-QA-only-3847!"
NOTICE = "qa-experience-1"
SLUG = "forgegov-fullstack-qa"


def setup():
    sys.path.insert(0, str(Path.cwd()))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgegov.settings")
    import django
    django.setup()
    from django.conf import settings
    if (os.getenv("FORGEGOV_ISOLATED_QA") != "1" or not settings.DEBUG
            or settings.DATABASES["default"].get("HOST") != "db"):
        raise SystemExit("Refusing fixtures outside the explicit isolated Docker QA database.")


def seed():
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from core.models import Membership, Organization, UserSecurityProfile
    from core.subscriptions import ensure_organization_subscription
    organization, _ = Organization.objects.get_or_create(slug=SLUG, defaults={"name": "Synthetic Full-stack QA"})
    # Disposable QA workspace has a bounded entitlement; never bypass production checks.
    from core.subscriptions import ensure_organization_subscription
    from django.utils import timezone
    from datetime import timedelta
    subscription = ensure_organization_subscription(organization)
    subscription.status = "active"
    subscription.provider = "manual"
    subscription.current_period_ends_at = timezone.now() + timedelta(days=1)
    subscription.save()
    user, _ = get_user_model().objects.get_or_create(username=EMAIL, defaults={"email": EMAIL})
    user.set_password(PASSWORD)
    user.save()
    Membership.objects.update_or_create(user=user, organization=organization, defaults={"role": "owner", "active": True})
    UserSecurityProfile.objects.update_or_create(user=user, defaults={
        "lifecycle_status": "active", "account_status": "active",
        "email_verified_at": timezone.now(), "terms_accepted_at": timezone.now(),
        "privacy_accepted_at": timezone.now(),
    })
    subscription = ensure_organization_subscription(organization)
    subscription.status = "active"
    subscription.save(update_fields=["status", "updated_at"])
    print("Disposable QA identity and workspace ready.")


def verify():
    from core.models import Organization, PricingCostItem, ProjectRoom, ProjectRoomTask, ProposalSection, Task
    organization = Organization.objects.get(slug=SLUG)
    assert Task.objects.filter(organization=organization, title="Full-stack QA task", completed=True).exists()
    assert ProjectRoom.objects.filter(owner_organization=organization, name="Full-stack QA room").exists()
    assert ProjectRoomTask.objects.filter(project_room__owner_organization=organization, title="Full-stack room task", status="done").exists()
    assert ProposalSection.objects.filter(volume__plan__organization=organization, content="Full-stack QA revision").exists()
    assert PricingCostItem.objects.filter(plan__organization=organization, name="Full-stack QA labor", labor_hours=2, labor_rate=50).exists()
    from core.models import PublicInquiry
    assert PublicInquiry.objects.filter(company="Isolated Release QA", purpose="access").exists()
    print("Verified public inquiry, task completion, room creation, proposal revision and pricing item in PostgreSQL.")


class ProviderFixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/opportunities/v2/search"):
            payload = {"totalRecords": 1, "opportunitiesData": [{
                "noticeId": NOTICE, "title": "Synthetic full-stack QA opportunity",
                "fullParentPathName": "QA Agency", "solicitationNumber": "QA-ONLY-001",
                "naicsCode": "541512", "type": "Solicitation", "postedDate": "2026-10-22",
                "responseDeadLine": "2026-12-30T17:00:00Z", "description": "Controlled government-provider fixture for isolated CI.",
                "resourceLinks": [],
            }]}
        elif self.path.startswith("/api/v2/awards/last_updated/"):
            payload = {"last_updated": "2026-10-22"}
        else:
            self.send_error(404)
            return
        self.respond(payload)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path.startswith("/api/v2/search/"):
            self.respond({"results": [], "page_metadata": {"hasNext": False}})
        else:
            self.send_error(404)

    def respond(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    setup()
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode == "seed":
        seed()
    elif mode == "verify":
        verify()
    elif mode == "serve":
        ThreadingHTTPServer(("127.0.0.1", 9001), ProviderFixture).serve_forever()
    else:
        raise SystemExit("Expected seed, verify or serve.")
