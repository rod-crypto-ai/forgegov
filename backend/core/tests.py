from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .integrations import search_sam_opportunities, upsert_sam_opportunity
from .models import Opportunity


class HealthTests(TestCase):
    def test_health_endpoint(self):
        response = APIClient().get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["product"], "ForgeGov")


class OpportunityTests(TestCase):
    def test_search(self):
        Opportunity.objects.create(source_id="x-1", title="Vehicle maintenance support", agency="USMC")
        Opportunity.objects.create(source_id="x-2", title="Custodial services", agency="GSA")
        response = APIClient().get("/api/opportunities/?search=vehicle")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_dashboard_summary_uses_database_counts(self):
        Opportunity.objects.create(source_id="x-1", title="Active", active=True)
        Opportunity.objects.create(source_id="x-2", title="Archived", active=False)
        response = APIClient().get("/api/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["opportunities"], {"total": 2, "active": 1})


class SamIntegrationTests(TestCase):
    def test_upsert_normalizes_sam_record(self):
        record = {
            "noticeId": "abc-123",
            "title": "JLTV Maintenance Support",
            "solicitationNumber": "W123-26-Q-0001",
            "fullParentPathName": "DEPT OF DEFENSE.DEPT OF THE NAVY.USMC",
            "type": "Sources Sought",
            "naicsCode": "811111",
            "classificationCode": "J023",
            "setAside": "Total Small Business Set-Aside",
            "setAsideCode": "SBA",
            "postedDate": "2026-07-20 09:00:00",
            "responseDeadLine": "2026-08-01 17:00:00",
            "active": "Yes",
            "resourceLinks": ["https://example.gov/file.pdf"],
        }
        opportunity, created = upsert_sam_opportunity(record)
        self.assertTrue(created)
        self.assertEqual(opportunity.agency, "DEPT OF DEFENSE")
        self.assertEqual(opportunity.subagency, "DEPT OF THE NAVY")
        self.assertEqual(opportunity.office, "USMC")
        self.assertEqual(opportunity.notice_type, Opportunity.NoticeType.SOURCES_SOUGHT)
        self.assertEqual(opportunity.naics_code, "811111")
        self.assertEqual(opportunity.psc_code, "J023")
        self.assertEqual(opportunity.source_url, "https://sam.gov/opp/abc-123/view")

    @override_settings(SAM_GOV_API_KEY="test-key")
    @patch("core.integrations.requests.get")
    def test_live_search_can_persist_results(self, mock_get):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "totalRecords": 1,
            "limit": 25,
            "offset": 0,
            "opportunitiesData": [{"noticeId": "abc-123", "title": "Vehicle maintenance"}],
        }
        mock_get.return_value = response

        result = search_sam_opportunities(keyword="vehicle", persist=True)

        self.assertEqual(result["persisted"]["created"], 1)
        self.assertTrue(Opportunity.objects.filter(source_id="abc-123").exists())
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["title"], "vehicle")
        self.assertNotIn("q", called_params)


class UsaSpendingIntegrationTests(TestCase):
    @patch("core.integrations.requests.post")
    def test_live_usaspending_search_persists_awards(self, mock_post):
        from .integrations import search_usaspending_awards
        from .models import Agency, Award, Vendor

        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "page_metadata": {"page": 1, "hasNext": False},
            "results": [{
                "Award ID": "W56HZV-26-C-0001",
                "generated_unique_award_id": "CONT_AWD_W56HZV26C0001_9700",
                "Recipient Name": "HOWARD DYNAMICS LLC",
                "Award Amount": 1250000,
                "Description": "Vehicle maintenance support",
                "Start Date": "2026-01-01",
                "End Date": "2026-12-31",
                "Awarding Agency": "Department of Defense",
                "Funding Agency": "Department of the Army",
            }],
        }
        mock_post.return_value = response

        result = search_usaspending_awards(keyword="maintenance", persist=True)

        self.assertEqual(result["persisted"]["created"], 1)
        self.assertTrue(Award.objects.filter(source_id="CONT_AWD_W56HZV26C0001_9700").exists())
        self.assertTrue(Vendor.objects.filter(name="HOWARD DYNAMICS LLC").exists())
        self.assertTrue(Agency.objects.filter(name="Department of Defense").exists())
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["filters"]["keywords"], ["maintenance"])

    @patch("core.integrations.requests.post")
    def test_api_endpoint_returns_live_results(self, mock_post):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {"page_metadata": {"page": 1}, "results": []}
        mock_post.return_value = response
        api_response = APIClient().get("/api/live/usaspending/awards/?q=logistics")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["results"], [])
