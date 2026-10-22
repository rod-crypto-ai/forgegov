from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from rest_framework.test import APIClient

from .models import Award, Opportunity
from .integrations import search_usaspending_awards, upsert_usaspending_award
from .tests import AuthenticatedApiTestCase


class ExperienceReportTests(AuthenticatedApiTestCase):
    def test_search_routes_to_the_actual_source_workspace(self):
        for source, source_id, expected in [
            ("sam.gov", "qa-sam", "/opportunities/federal-contracts/qa-sam"),
            ("grants.gov", "grants.gov:123", "/opportunities/federal-grants/123"),
            ("sba-subnet", "sba-subnet:qa-listing", "/opportunities/subcontracting/sba-subnet%3Aqa-listing"),
        ]:
            Opportunity.objects.create(source=source, source_id=source_id, title="RoutingQA opportunity")
            payload = self.client.get("/api/intelligence/search/?q=RoutingQA").json()
            result = next(row for row in payload["results"] if row["id"] == source_id)
            self.assertEqual(result["href"], expected)

    def test_search_invalid_limit_returns_validation_error_not_server_error(self):
        self.assertEqual(self.client.get("/api/intelligence/search/?q=RoutingQA&limit=invalid").status_code, 400)

    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        for source_id, recipient, agency, days, value in [
            ("old", "Repeat vendor", "Agency A", 400, 100),
            ("repeat", "Repeat vendor", "Agency A", 3, 200),
            ("entrant", "Recent vendor", "Agency A", 5, 300),
            ("new-agency", "Repeat vendor", "Agency B", 2, 400),
        ]:
            Award.objects.create(source_id=source_id, source="usaspending.gov", recipient_name=recipient, awarding_agency=agency, start_date=today-timedelta(days=days), obligated_amount=value, naics_code="541512")
        Award.objects.create(source_id="unknown-date", source="usaspending.gov", recipient_name="Undated vendor", awarding_agency="Agency A", obligated_amount=50)

    def test_first_observed_uses_all_history_before_window_and_separates_agencies(self):
        response = self.client.get("/api/reports/market/?kind=new-entrants&days=90")
        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        self.assertEqual({(r["recipient_name"], r["awarding_agency"]) for r in rows}, {("Recent vendor", "Agency A"), ("Repeat vendor", "Agency B")})
        self.assertIn("incomplete history", response.json()["coverage_note"])

    def test_funding_aggregates_stored_obligations_and_filters_without_private_portfolio(self):
        payload = self.client.get("/api/reports/market/?kind=funding").json()
        self.assertEqual(payload["totals"]["obligated"], 1050)
        self.assertEqual(payload["results"][0]["awarding_agency"], "Agency A")
        filtered = self.client.get("/api/reports/market/?kind=funding&agency=Agency%20B&naics=541512").json()
        self.assertEqual(filtered["totals"]["obligated"], 400)
        self.assertNotIn("pipeline", filtered)

    def test_report_requires_authentication_and_valid_parameters(self):
        self.assertIn(APIClient().get("/api/reports/market/").status_code, (401, 403))
        for query in ("kind=invalid", "days=no", "days=0", "days=3651", "page=0", "page=10001"):
            self.assertEqual(self.client.get("/api/reports/market/?"+query).status_code, 400)

    def test_empty_filtered_report_is_explicit_and_page_is_bounded(self):
        payload = self.client.get("/api/reports/market/?kind=new-entrants&agency=Unknown&page=10").json()
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["page"], 1)

    @patch("core.integrations.resilient_request")
    def test_official_award_fields_populate_category_and_freshness_evidence(self, request):
        record = {"generated_internal_id": "documented-fields", "Award ID": "QA-1", "Recipient Name": "Category vendor", "Award Amount": 1000, "NAICS": {"code": "541512", "description": "Systems design"}, "PSC": {"code": "DA10", "description": "IT"}, "Last Modified Date": "2026-10-21", "Start Date": "2026-10-01"}
        response = Mock(ok=True)
        response.json.return_value = {"results": [record], "page_metadata": {"hasNext": False}}
        request.return_value = response
        search_usaspending_awards(persist=True)
        payload = request.call_args.kwargs["json"]
        self.assertTrue({"NAICS", "PSC", "Last Modified Date"}.issubset(payload["fields"]))
        self.assertNotIn("NAICS Code", payload["fields"])
        self.assertEqual(payload["sort"], "Last Modified Date")
        award = Award.objects.get(source_id="documented-fields")
        self.assertEqual(award.naics_code, "541512")
        self.assertEqual(award.psc_code, "DA10")
        self.assertEqual(award.source_updated_at.date().isoformat(), "2026-10-21")
        categories = self.client.get("/api/intelligence/categories/?type=naics").json()["results"]
        self.assertTrue(any(row["code"] == "541512" and row["award_count"] > 0 for row in categories))

    def test_partial_award_response_preserves_known_categories_and_source_date(self):
        original = {"generated_internal_id": "partial-qa", "Award ID": "QA-2", "Recipient Name": "Partial vendor", "NAICS Code": "541512", "PSC Code": "DA10", "Last Modified Date": "2026-10-21"}
        upsert_usaspending_award(original)
        award, _ = upsert_usaspending_award({"generated_internal_id": "partial-qa", "Award ID": "QA-2", "Recipient Name": "Partial vendor", "NAICS": {"code": None}, "PSC": {"code": None}})
        self.assertEqual(award.naics_code, "541512")
        self.assertEqual(award.psc_code, "DA10")
        self.assertEqual(award.source_updated_at.date().isoformat(), "2026-10-21")
