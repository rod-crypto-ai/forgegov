from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Membership, NotificationDelivery, Organization
from platform_admin.models import PlatformAdminGrant, PlatformSetting

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PlatformNotificationV312Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Creator Test Co", slug="creator-test-co")
        self.creator = User.objects.create_user(
            username="creator312@example.com",
            email="creator312@example.com",
            password="StrongPassphrase123!",
        )
        Membership.objects.create(organization=self.org, user=self.creator, role=Membership.Role.OWNER)
        PlatformAdminGrant.objects.create(
            user=self.creator,
            role=PlatformAdminGrant.Role.CREATOR,
            is_active=True,
            mfa_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.creator)

    def test_creator_can_pause_and_resume_notification_delivery(self):
        response = self.client.post(
            "/api/platform-admin/creator-control/",
            {"notifications_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["notifications_enabled"])
        row = PlatformSetting.objects.get(key="notifications_enabled")
        self.assertFalse(row.value["enabled"])

        response = self.client.post(
            "/api/platform-admin/creator-control/",
            {"notifications_enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["notifications_enabled"])

    def test_creator_can_send_tracked_notification_test(self):
        PlatformSetting.objects.update_or_create(key="notifications_enabled", defaults={"value": {"enabled": True}})
        response = self.client.post("/api/platform-admin/notifications/test/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["email_sent"])
        self.assertTrue(
            NotificationDelivery.objects.filter(
                user=self.creator,
                category="system_test",
                status=NotificationDelivery.Status.SENT,
            ).exists()
        )

    def test_super_admin_cannot_use_creator_test_delivery(self):
        admin = User.objects.create_user(
            username="admin312@example.com",
            email="admin312@example.com",
            password="StrongPassphrase123!",
        )
        PlatformAdminGrant.objects.create(
            user=admin,
            role=PlatformAdminGrant.Role.SUPER_ADMIN,
            is_active=True,
            mfa_verified=True,
        )
        client = APIClient()
        client.force_authenticate(admin)
        response = client.post("/api/platform-admin/notifications/test/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        operations = client.get("/api/platform-admin/notifications/")
        self.assertEqual(operations.status_code, 403)
