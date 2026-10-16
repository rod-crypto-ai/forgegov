from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Award, AwardSyncRun, ConnectorSource, DataSyncRun, IntelligenceAlert, Opportunity, PipelineItem, Pursuit, SavedSearch
from .tests import AuthenticatedApiTestCase


def sam_page(*, total, limit, offset, rows, created=0, updated=0):
    return {
        "total_records": total,
        "limit": limit,
        "offset": offset,
        "opportunities": [{"source_id": value} for value in rows],
        "persisted": {
            "created": created,
            "updated": updated,
            "unchanged": 0,
            "quarantined": 0,
            "errors": [],
        },
    }


class SamSyncCompletenessTests(TestCase):
    @patch("core.tasks.search_sam_opportunities")
    def test_sync_traverses_pages_until_the_reported_total_is_received(self, search):
        from .tasks import sync_recent_sam_opportunities

        search.side_effect = [
            sam_page(total=3, limit=2, offset=0, rows=["one", "two"], created=2),
            sam_page(total=3, limit=1, offset=2, rows=["three"], created=1),
        ]

        result = sync_recent_sam_opportunities.run(days=2, limit=3)

        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args_list[1].kwargs["offset"], 2)
        self.assertEqual(result["records_received"], 3)
        self.assertTrue(result["complete"])
        run = DataSyncRun.objects.get(pk=result["run_id"])
        self.assertEqual(run.status, DataSyncRun.Status.SUCCESS)
        self.assertTrue(run.request_metadata["integrity"]["complete"])

    @patch("core.tasks.search_sam_opportunities")
    def test_sync_marks_a_bounded_run_partial_instead_of_claiming_completeness(self, search):
        from .tasks import sync_recent_sam_opportunities

        search.return_value = sam_page(total=5, limit=2, offset=0, rows=["one", "two"], created=2)

        result = sync_recent_sam_opportunities.run(days=2, limit=2)

        self.assertFalse(result["complete"])
        run = DataSyncRun.objects.get(pk=result["run_id"])
        self.assertEqual(run.status, DataSyncRun.Status.PARTIAL)
        self.assertIn("reported 5 records", run.error_message)


class UsaSpendingSyncCompletenessTests(TestCase):
    @patch("core.intelligence.services.award_ingestion.upsert_usaspending_award")
    @patch("core.intelligence.services.award_ingestion.get_connector")
    def test_ingestion_marks_remaining_pages_as_partial(self, get_connector, upsert):
        from .intelligence.services.award_ingestion import sync_usaspending_awards

        class TruncatedConnector:
            descriptor = type("Descriptor", (), {"key": "usaspending-awards", "name": "USAspending Federal Awards"})()
            last_pages_processed = 0
            last_has_next = False

            def iter_awards(self, **_filters):
                self.last_pages_processed = 1
                self.last_has_next = True
                yield {"generated_internal_id": "award-1"}

        get_connector.return_value = TruncatedConnector()
        award = type("Award", (), {"_forgegov_source_version_created": True})()
        upsert.return_value = (award, True)

        run = sync_usaspending_awards(start_date="2026-10-01", end_date="2026-10-15", pages=1, limit=100)

        self.assertEqual(run.status, AwardSyncRun.Status.PARTIAL)
        self.assertEqual(run.pages_processed, 1)
        self.assertIn("additional pages", run.errors[0])


class SubscriptionReadinessRegressionTests(AuthenticatedApiTestCase):
    def test_connector_registry_reports_actual_stored_record_counts(self):
        Opportunity.objects.create(source="sam.gov", source_id="sam-count", title="SAM record")
        Opportunity.objects.create(source="grants.gov", source_id="grant-count", title="Grant record")
        Award.objects.create(source="usaspending.gov", source_id="award-count", award_type=Award.AwardType.CONTRACT)
        Award.objects.create(source="usaspending.gov", source_id="vehicle-count", award_type=Award.AwardType.VEHICLE)
        ConnectorSource.objects.create(key="sam-opportunities", name="SAM.gov Opportunities", record_count=0)

        from .intelligence.services.award_ingestion import connector_registry_payload

        rows = {row["key"]: row for row in connector_registry_payload(probe=False)["connectors"]}
        self.assertEqual(rows["sam-opportunities"]["record_count"], 1)
        self.assertEqual(rows["grants-opportunities"]["record_count"], 1)
        self.assertEqual(rows["usaspending-awards"]["record_count"], 2)
        self.assertEqual(rows["usaspending-vehicles"]["record_count"], 1)

    def test_command_summary_distinguishes_available_from_indexed_documents(self):
        opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="doc-availability",
            title="Document availability",
            resource_links=[{"url": "https://sam.gov/example.pdf"}],
        )
        response = self.client.get(f"/api/workflow/opportunities/{opportunity.source_id}/command-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documents"], {"ready": 0, "total": 0, "available": 1})

    def test_pursuit_updates_keep_linked_pipeline_metrics_aligned(self):
        opportunity = Opportunity.objects.create(source_id="aligned-pursuit", title="Aligned pursuit")
        pipeline = PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=100,
            probability_of_win=10,
        )
        pursuit = Pursuit.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            title=opportunity.title,
            stage=Pursuit.Stage.CAPTURE,
            estimated_value=100,
            probability_of_win=10,
        )

        response = self.client.patch(
            f"/api/pursuits/{pursuit.id}/",
            {"stage": Pursuit.Stage.SUBMITTED, "estimated_value": 2500, "probability_of_win": 60},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.stage, PipelineItem.Stage.SUBMITTED)
        self.assertEqual(pipeline.estimated_value, 2500)
        self.assertEqual(pipeline.probability_of_win, 60)

    def test_pipeline_updates_keep_linked_pursuit_metrics_aligned(self):
        opportunity = Opportunity.objects.create(source_id="aligned-pipeline", title="Aligned pipeline")
        pipeline = PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            owner=self.user,
            stage=PipelineItem.Stage.CAPTURE,
        )
        pursuit = Pursuit.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            title=opportunity.title,
            stage=Pursuit.Stage.CAPTURE,
        )

        response = self.client.patch(
            f"/api/pipeline/{pipeline.id}/",
            {"stage": PipelineItem.Stage.PROPOSAL, "estimated_value": 4200, "probability_of_win": 55},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        pursuit.refresh_from_db()
        self.assertEqual(pursuit.stage, Pursuit.Stage.PROPOSAL)
        self.assertEqual(pursuit.estimated_value, 4200)
        self.assertEqual(pursuit.probability_of_win, 55)
        self.assertEqual(pursuit.owner, self.user)

    @override_settings(SAVED_SEARCH_ALERT_MAX_PER_RUN=1)
    @patch("core.tasks.search_sam_opportunities")
    def test_saved_search_establishes_a_baseline_then_caps_new_alerts(self, search):
        saved = SavedSearch.objects.create(
            organization=self.organization,
            owner=self.user,
            name="Maintenance",
            filters={"source": "sam.gov", "q": "maintenance"},
        )
        search.return_value = {"opportunities": []}

        from .tasks import evaluate_saved_search_alerts

        baseline = evaluate_saved_search_alerts.run(organization_id=self.organization.id)
        self.assertEqual(baseline["alerts_created"], 0)
        saved.refresh_from_db()
        self.assertIsNotNone(saved.last_evaluated_at)

        posted_at = timezone.now()
        first = Opportunity.objects.create(source="sam.gov", source_id="new-one", title="New one", posted_date=posted_at)
        second = Opportunity.objects.create(source="sam.gov", source_id="new-two", title="New two", posted_date=posted_at)
        search.return_value = {"opportunities": [{"source_id": first.source_id, "title": first.title}, {"source_id": second.source_id, "title": second.title}]}

        result = evaluate_saved_search_alerts.run(organization_id=self.organization.id)
        self.assertEqual(result["alerts_created"], 1)
        self.assertEqual(IntelligenceAlert.objects.filter(organization=self.organization).count(), 1)

    def test_irregular_invitation_verbs_are_grammatical(self):
        from .views import _action_past_tense

        self.assertEqual(_action_past_tense("decline"), "declined")
        self.assertEqual(_action_past_tense("resend"), "resent")
