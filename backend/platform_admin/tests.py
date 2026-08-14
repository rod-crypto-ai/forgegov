from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Organization
from .models import PlatformAdminGrant, OrganizationControlState, UserControlState, FeatureFlag

User = get_user_model()


class PlatformAdminSecurityTests(TestCase):
    def setUp(self):
        self.normal = User.objects.create_user(username="normal", email="normal@example.com", password="pass")
        self.org_admin = User.objects.create_user(username="orgadmin", email="orgadmin@example.com", password="pass")
        self.platform = User.objects.create_user(username="platform", email="platform@example.com", password="pass")
        PlatformAdminGrant.objects.create(user=self.platform, role="super_admin", is_active=True, mfa_verified=True)

    def test_normal_user_blocked(self):
        client = APIClient()
        client.force_authenticate(self.normal)
        self.assertEqual(client.get("/api/platform-admin/dashboard/").status_code, 403)

    def test_organization_admin_role_does_not_grant_platform_access(self):
        client = APIClient()
        client.force_authenticate(self.org_admin)
        self.assertEqual(client.get("/api/platform-admin/users/").status_code, 403)

    def test_platform_admin_allowed(self):
        client = APIClient()
        client.force_authenticate(self.platform)
        self.assertEqual(client.get("/api/platform-admin/dashboard/").status_code, 200)

    def test_mfa_unverified_grant_is_denied(self):
        self.platform.forgegov_platform_admin_grant.mfa_verified = False
        self.platform.forgegov_platform_admin_grant.save()
        client = APIClient()
        client.force_authenticate(self.platform)
        self.assertEqual(client.get("/api/platform-admin/dashboard/").status_code, 403)

    def test_user_suspend_action_creates_enforced_state(self):
        client = APIClient()
        client.force_authenticate(self.platform)
        response = client.post(
            f"/api/platform-admin/users/{self.normal.id}/action/",
            {"action": "suspend", "reason": "test"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserControlState.objects.get(user=self.normal).status, "suspended")

    def test_feature_flag_update_requires_super_admin(self):
        FeatureFlag.objects.create(key="forgeai", name="ForgeAI", enabled=True)
        client = APIClient()
        client.force_authenticate(self.platform)
        response = client.post("/api/platform-admin/feature-flags/", {"key": "forgeai", "enabled": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FeatureFlag.objects.get(key="forgeai").enabled)
