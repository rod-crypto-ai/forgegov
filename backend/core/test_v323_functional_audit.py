from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from .models import IntelligenceAlert, Opportunity, PipelineItem
from .tests import AuthenticatedApiTestCase


class FunctionalAuditV323Tests(AuthenticatedApiTestCase):
    def test_quick_global_search_skips_large_description_fields(self):
        Opportunity.objects.create(
            source_id="quick-search-description-only",
            title="Unrelated title",
            description="needle-only-in-the-large-description",
        )

        full = self.client.get("/api/intelligence/search/?q=needle-only").json()
        quick = self.client.get("/api/intelligence/search/?q=needle-only&quick=true").json()

        self.assertTrue(any(row["id"] == "quick-search-description-only" for row in full["results"]))
        self.assertFalse(any(row["id"] == "quick-search-description-only" for row in quick["results"]))

    @patch("core.views.search_grants_opportunities", return_value={"opportunities": [], "total_records": 0})
    def test_grants_browsing_does_not_persist_results_by_default(self, search):
        response = self.client.get("/api/live/grants/opportunities/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(search.call_args.kwargs["persist"])

    @patch("core.views.search_sam_opportunities")
    def test_pipeline_add_persists_only_the_selected_sam_record(self, search):
        def store_selected(**kwargs):
            Opportunity.objects.create(source_id=kwargs["notice_id"], title="Selected notice")
            return {"opportunities": [{"source_id": kwargs["notice_id"]}]}

        search.side_effect = store_selected
        response = self.client.post(
            "/api/workflow/opportunity-to-pipeline/",
            {"source_id": "selected-sam-notice", "stage": "reviewing"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        search.assert_called_once_with(notice_id="selected-sam-notice", limit=1, persist=True)
        self.assertTrue(PipelineItem.objects.filter(organization=self.organization, opportunity__source_id="selected-sam-notice").exists())

    def test_current_alert_count_excludes_stale_new_matches_but_preserves_history(self):
        recent = IntelligenceAlert.objects.create(
            organization=self.organization,
            alert_type=IntelligenceAlert.AlertType.NEW_OPPORTUNITY,
            title="Recent match",
            source_id="recent-match",
        )
        stale = IntelligenceAlert.objects.create(
            organization=self.organization,
            alert_type=IntelligenceAlert.AlertType.NEW_OPPORTUNITY,
            title="Historical match",
            source_id="historical-match",
        )
        IntelligenceAlert.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=8))

        active = self.client.get("/api/alerts/?read=false&dismissed=false&active=true").json()
        history = self.client.get("/api/alerts/?read=false&dismissed=false").json()
        summary = self.client.get("/api/dashboard/summary/").json()

        self.assertEqual(active["count"], 1)
        self.assertEqual(active["results"][0]["id"], recent.id)
        self.assertEqual(history["count"], 2)
        self.assertEqual(summary["alerts"], {"unread": 1, "total": 2})

    def test_non_opportunity_alerts_remain_current_for_thirty_days(self):
        current = IntelligenceAlert.objects.create(
            organization=self.organization,
            alert_type=IntelligenceAlert.AlertType.DEADLINE,
            title="Current deadline",
            source_id="deadline-current",
        )
        old = IntelligenceAlert.objects.create(
            organization=self.organization,
            alert_type=IntelligenceAlert.AlertType.DEADLINE,
            title="Old deadline",
            source_id="deadline-old",
        )
        IntelligenceAlert.objects.filter(pk=current.pk).update(created_at=timezone.now() - timedelta(days=29))
        IntelligenceAlert.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))

        payload = self.client.get("/api/alerts/?active=true").json()

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], current.id)
