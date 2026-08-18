from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.integration_resilience import quarantine_record


class PlatformAdminIntegrityV308Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="v308-admin@example.com", email="v308-admin@example.com", password="StrongPass!234567")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_data_integrity_endpoint_is_available_to_platform_admin(self):
        quarantine_record(source="sam.gov", record_type="opportunity.sam", payload={"bad": 1}, reason="test")
        response = self.client.get("/api/platform-admin/data-integrity/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["unresolved_quarantine"], 1)

    def test_super_admin_can_retry_quarantined_record(self):
        row = quarantine_record(source="sam.gov", record_type="opportunity.sam", payload={"noticeId": "admin-retry", "title": "Retry"}, reason="test")
        response = self.client.post(f"/api/platform-admin/data-integrity/quarantine/{row.id}/retry/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["resolved"])
