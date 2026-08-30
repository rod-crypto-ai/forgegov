import hashlib

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CompanyLogo, Organization


class CompanyLogoNaicsVisibilityTests(TestCase):
    def test_by_name_logo_lookup_works_with_duplicate_company_names(self):
        Organization.objects.create(name="Coffee Company", slug="coffee-company-one")
        newer = Organization.objects.create(name="Coffee Company", slug="coffee-company-two")
        content = b"\x89PNG\r\n\x1a\ncoffee-logo"
        CompanyLogo.objects.create(
            organization=newer,
            content=content,
            content_type="image/png",
            sha256=hashlib.sha256(content).hexdigest(),
        )

        response = APIClient().get("/api/network/company-logo/?name=Coffee%20Company")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, content)

    def test_naics_reference_is_current_2022_dataset(self):
        response = APIClient().get("/api/reference/naics/?q=541330")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "2022")
        self.assertGreaterEqual(payload["total_reference_records"], 2000)
        self.assertTrue(any(row["code"] == "541330" for row in payload["results"]))
