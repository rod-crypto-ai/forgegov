from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from .integrations import IntegrationError, fetch_sam_opportunity_detail
from .models import Opportunity, PipelineItem
from .tests import AuthenticatedApiTestCase


@override_settings(SAM_GOV_API_KEY="")
class SavedOpportunityTests(AuthenticatedApiTestCase):
    def setUp(self):
        super().setUp()
        self.notice = Opportunity.objects.create(
            source="sam.gov", source_id="saved-notice", title="Saved capture requirement",
            agency="Department of Testing", description="Saved requirement description",
            posted_date=timezone.now() - timedelta(days=70),
            resource_links=["https://example.gov/requirements.pdf"],
            source_url="https://sam.gov/opp/saved-notice/view",
            raw_data={"noticeId": "saved-notice", "title": "Saved capture requirement"},
        )
        self.pipeline = PipelineItem.objects.create(organization=self.organization, opportunity=self.notice)

    @patch("core.integrations.search_sam_opportunities", return_value={"opportunities": []})
    def test_saved_pipeline_notice_survives_empty_live_search(self, search):
        result = self.client.get("/api/live/sam/opportunities/saved-notice/")
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["opportunity"]["title"], self.notice.title)
        self.assertEqual(body["description"], self.notice.description)
        self.assertEqual(body["documents"][0]["name"], "requirements.pdf")
        self.assertEqual(body["source_status"], "stored")
        self.assertIn("live verification was unavailable", body["source_warning"])
        self.assertEqual(body["stored_at"], self.notice.updated_at.isoformat())
        self.assertEqual(search.call_args.kwargs["posted_from"], self.notice.posted_date.date().isoformat())
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.raw_data["title"], "Saved capture requirement")
        self.assertTrue(PipelineItem.objects.filter(pk=self.pipeline.pk, opportunity=self.notice).exists())

    @patch("core.integrations.search_sam_opportunities", side_effect=IntegrationError("SAM.gov unavailable"))
    def test_saved_record_survives_provider_failure(self, search):
        result = fetch_sam_opportunity_detail(self.notice.source_id)
        self.assertEqual(result["source_status"], "stored")
        self.assertEqual(result["opportunity"]["source_id"], self.notice.source_id)

    @patch("core.integrations.search_sam_opportunities", return_value={"opportunities": []})
    def test_unknown_notice_still_returns_not_found(self, search):
        response = self.client.get("/api/live/sam/opportunities/unknown-notice/")
        self.assertEqual(response.status_code, 404)

    @patch("core.integrations.search_sam_opportunities")
    def test_live_matching_record_takes_precedence(self, search):
        search.return_value = {"opportunities": [{"noticeId": self.notice.source_id, "title": "Live amendment"}]}
        result = fetch_sam_opportunity_detail(self.notice.source_id)
        self.assertEqual(result["opportunity"]["title"], "Live amendment")
        self.assertEqual(result["source_status"], "live")
        self.assertEqual(result["source_warning"], "")
        self.assertIsNone(result["stored_at"])

    @patch("core.integrations.search_sam_opportunities", return_value={"opportunities": [{"noticeId": "wrong-notice", "title": "Unrelated"}]})
    def test_unrelated_live_result_never_replaces_saved_record(self, search):
        result = fetch_sam_opportunity_detail(self.notice.source_id)
        self.assertEqual(result["opportunity"]["title"], self.notice.title)
        self.assertEqual(result["source_status"], "stored")

    @patch("core.integrations.search_sam_opportunities", return_value={"opportunities": []})
    def test_other_sources_are_not_treated_as_sam_records(self, search):
        Opportunity.objects.create(source="grants.gov", source_id="grant-notice", title="Grant")
        response = self.client.get("/api/live/sam/opportunities/grant-notice/")
        self.assertEqual(response.status_code, 404)
