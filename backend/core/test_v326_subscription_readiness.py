from unittest.mock import patch

from django.test import TestCase

from .models import AwardSyncRun, DataSyncRun


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
