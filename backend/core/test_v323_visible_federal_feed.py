from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from .models import Award, AwardSyncRun, DataSyncRun, Opportunity
from .reliability import sync_freshness
from .tests import AuthenticatedApiTestCase


class VisibleFederalFeedV323Tests(AuthenticatedApiTestCase):
    def test_feed_requires_authentication(self):
        response = APIClient().get("/api/intelligence/recent-federal-activity/")
        self.assertEqual(response.status_code, 401)

    def test_opportunity_feed_orders_filters_and_paginates_stored_sam_records(self):
        now = timezone.now()
        for index in range(22):
            Opportunity.objects.create(
                source="sam.gov",
                source_id=f"sam-{index:02d}",
                title=f"Cloud support {index:02d}",
                agency="Department of Test" if index < 21 else "Other Agency",
                naics_code="541512",
                posted_date=now - timedelta(hours=index),
            )
        Opportunity.objects.create(source="grants.gov", source_id="grant-1", title="Cloud grant", posted_date=now)

        first = self.client.get("/api/intelligence/recent-federal-activity/?q=cloud&agency=Department&page_size=20").json()
        second = self.client.get("/api/intelligence/recent-federal-activity/?q=cloud&agency=Department&page=2&page_size=20").json()

        self.assertEqual(first["count"], 21)
        self.assertEqual(first["results"][0]["source_id"], "sam-00")
        self.assertEqual(first["next_page"], 2)
        self.assertEqual(second["previous_page"], 1)
        self.assertEqual([row["source_id"] for row in second["results"]], ["sam-20"])

    def test_award_feed_uses_award_sync_evidence(self):
        now = timezone.now()
        run = AwardSyncRun.objects.create(
            connector_key="usaspending-awards",
            status=AwardSyncRun.Status.SUCCEEDED,
            started_at=now - timedelta(minutes=5),
            completed_at=now,
            records_seen=12,
            records_created=7,
            records_updated=5,
        )
        Award.objects.create(
            source="usaspending.gov",
            source_id="award-1",
            award_number="FAKE-001",
            description="Cloud modernization",
            recipient_name="Example Contractor",
            awarding_agency="Department of Test",
            obligated_amount=125000,
            source_updated_at=now,
        )

        payload = self.client.get("/api/intelligence/recent-federal-activity/?kind=awards&q=modernization").json()
        integration = self.client.get("/api/integrations/status/").json()

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["award_number"], "FAKE-001")
        self.assertEqual(payload["sync"]["status"], AwardSyncRun.Status.SUCCEEDED)
        self.assertEqual(payload["sync"]["records_seen"], 12)
        self.assertEqual(integration["usaspending"]["latest_sync"]["id"], run.id)
        self.assertEqual(integration["usaspending"]["latest_sync"]["records_received"], 12)

    def test_sync_freshness_reads_canonical_run_model_for_each_source(self):
        now = timezone.now()
        DataSyncRun.objects.create(source="sam.gov", status=DataSyncRun.Status.SUCCESS, finished_at=now)
        AwardSyncRun.objects.create(
            connector_key="usaspending-awards",
            status=AwardSyncRun.Status.SUCCEEDED,
            started_at=now,
            completed_at=now,
        )

        payload = sync_freshness()["sources"]

        self.assertEqual(payload["sam.gov"]["status"], "fresh")
        self.assertEqual(payload["usaspending.gov"]["status"], "fresh")

    def test_invalid_feed_kind_is_rejected(self):
        response = self.client.get("/api/intelligence/recent-federal-activity/?kind=grants")
        self.assertEqual(response.status_code, 400)

