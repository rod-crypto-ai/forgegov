from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Membership, Organization


class EnterpriseGovernanceV309Tests(TestCase):
    def test_organization_admin_does_not_gain_platform_admin_access(self):
        org = Organization.objects.create(name="Customer", slug="customer-v309")
        user = get_user_model().objects.create_user(username="customer-admin@example.com", email="customer-admin@example.com", password="StrongPass!234")
        Membership.objects.create(organization=org, user=user, role=Membership.Role.ADMIN)
        client = APIClient(); client.force_authenticate(user)
        response = client.get("/api/platform-admin/dashboard/")
        self.assertEqual(response.status_code, 403)
