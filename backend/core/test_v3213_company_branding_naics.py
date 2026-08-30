import base64

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import CompanyLogo, Membership, Organization


class CompanyBrandingNaicsV3213Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="branding-owner@example.com",
            email="branding-owner@example.com",
            password="StrongPassphrase12345!",
        )
        self.org = Organization.objects.create(name="Branding Test Company")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_official_naics_reference_contains_known_codes(self):
        response = self.client.get("/api/reference/naics/?q=541330")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "2022")
        self.assertTrue(any(row["code"] == "541330" for row in response.json()["results"]))

    def test_company_owner_can_store_and_read_png_logo(self):
        png = b"\x89PNG\r\n\x1a\n" + b"forgegov-logo-test"
        response = self.client.post(
            "/api/network/profile/logo/",
            {"content_type": "image/png", "content_base64": base64.b64encode(png).decode("ascii")},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CompanyLogo.objects.filter(organization=self.org).exists())
        public = APIClient().get(f"/api/network/organizations/{self.org.id}/logo/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public["Content-Type"], "image/png")
        self.assertEqual(public.content, png)

    def test_mismatched_image_signature_is_rejected(self):
        response = self.client.post(
            "/api/network/profile/logo/",
            {"content_type": "image/png", "content_base64": base64.b64encode(b"not-an-image").decode("ascii")},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CompanyLogo.objects.filter(organization=self.org).exists())
