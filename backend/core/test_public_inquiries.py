from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Organization, OrganizationSubscription, PublicInquiry


class PublicInquiryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.get("/api/auth/csrf/")
        self.csrf = self.client.cookies["csrftoken"].value
        self.payload = {"name": "Demo User", "email": "Demo@Example.invalid", "company": "Example Company", "purpose": "access", "message": "Review company onboarding", "consent": True}

    def submit(self, **changes):
        return self.client.post("/api/public/inquiries/", {**self.payload, **changes}, format="json", HTTP_X_CSRFTOKEN=self.csrf)

    def test_saves_only_inquiry_never_account_subscription_or_email(self):
        counts = (get_user_model().objects.count(), Organization.objects.count(), OrganizationSubscription.objects.count())
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        row = PublicInquiry.objects.get()
        self.assertEqual(row.email, "demo@example.invalid")
        self.assertEqual(str(row.reference), response.data["reference"])
        self.assertEqual(set(response.data), {"reference", "status"})
        self.assertEqual(counts, (get_user_model().objects.count(), Organization.objects.count(), OrganizationSubscription.objects.count()))

    def test_csrf_required_and_read_access_disallowed(self):
        self.assertEqual(APIClient(enforce_csrf_checks=True).post("/api/public/inquiries/", self.payload, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/public/inquiries/").status_code, 405)
        self.assertEqual(PublicInquiry.objects.count(), 0)

    def test_validation_consent_and_honeypot(self):
        for changes in ({"consent": False}, {"email": "invalid"}, {"website": "spam.invalid"}, {"company": " "}, {"message": "x" * 2001}, {"purpose": "admin"}):
            cache.clear()
            self.assertEqual(self.submit(**changes).status_code, 400)
        self.assertEqual(PublicInquiry.objects.count(), 0)

    def test_throttle_and_support_routing(self):
        for _ in range(5):
            self.assertEqual(self.submit(purpose="support").status_code, 201)
        self.assertEqual(self.submit().status_code, 429)
        self.assertEqual(PublicInquiry.objects.filter(purpose="support").count(), 5)
