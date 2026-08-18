from datetime import timedelta
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .integration_resilience import (
    ConnectorCircuitOpen,
    data_integrity_payload,
    fingerprint_payload,
    quarantine_record,
    record_source_version,
    resilient_request,
    retry_quarantined_record,
)
from .integrations import IntegrationError, upsert_sam_opportunity
from .models import Opportunity, SourceRecordVersion, SyncQuarantine


class DataIntegrityV308Tests(TestCase):
    def test_record_versions_dedupe_same_payload_and_keep_changed_history(self):
        base = {"noticeId": "n-1", "title": "First"}
        _, created1 = record_source_version(source="sam.gov", record_type="opportunity.sam", source_id="n-1", payload=base)
        _, created2 = record_source_version(source="sam.gov", record_type="opportunity.sam", source_id="n-1", payload=base)
        _, created3 = record_source_version(source="sam.gov", record_type="opportunity.sam", source_id="n-1", payload={**base, "title": "Changed"})
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertTrue(created3)
        self.assertEqual(SourceRecordVersion.objects.filter(source_id="n-1").count(), 2)

    def test_quarantine_dedupes_payload_and_counts_occurrences(self):
        payload = {"bad": "record"}
        first = quarantine_record(source="sam.gov", record_type="opportunity.sam", payload=payload, reason="test")
        second = quarantine_record(source="sam.gov", record_type="opportunity.sam", payload=payload, reason="test")
        self.assertEqual(first.id, second.id)
        second.refresh_from_db()
        self.assertEqual(second.occurrences, 2)
        self.assertEqual(SyncQuarantine.objects.count(), 1)

    def test_sam_stale_source_version_does_not_overwrite_newer_record(self):
        Opportunity.objects.create(
            source="sam.gov", source_id="stale-test", title="Newer", source_modified_at=timezone.now()
        )
        older = (timezone.now() - timedelta(days=1)).isoformat()
        with self.assertRaises(IntegrationError):
            upsert_sam_opportunity({"noticeId": "stale-test", "title": "Older", "modifiedDate": older})
        self.assertEqual(Opportunity.objects.get(source_id="stale-test").title, "Newer")

    def test_integrity_summary_reports_versions_and_quarantine(self):
        record_source_version(source="grants.gov", record_type="opportunity.grants", source_id="g1", payload={"id": 1})
        quarantine_record(source="grants.gov", record_type="opportunity.grants", payload={"bad": 1}, reason="bad")
        payload = data_integrity_payload()
        self.assertEqual(payload["summary"]["tracked_records"], 1)
        self.assertEqual(payload["summary"]["unresolved_quarantine"], 1)

    def test_retry_quarantine_resolves_supported_record(self):
        row = quarantine_record(
            source="sam.gov", record_type="opportunity.sam",
            payload={"noticeId": "retry-1", "title": "Retry me"}, reason="test",
        )
        result = retry_quarantined_record(row)
        row.refresh_from_db()
        self.assertTrue(result["resolved"])
        self.assertIsNotNone(row.resolved_at)
        self.assertTrue(Opportunity.objects.filter(source_id="retry-1").exists())


class ConnectorResilienceV308Tests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(CONNECTOR_RETRY_ATTEMPTS=2, CONNECTOR_RETRY_BACKOFF_SECONDS=0, CONNECTOR_CIRCUIT_FAILURE_THRESHOLD=2, CONNECTOR_CIRCUIT_OPEN_SECONDS=60)
    @patch("core.integration_resilience.requests.get")
    def test_retry_then_success_clears_circuit(self, request):
        bad = Mock(status_code=503)
        good = Mock(status_code=200)
        request.side_effect = [bad, good]
        response = resilient_request("unit-test", "GET", "https://example.test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.call_count, 2)

    @override_settings(CONNECTOR_RETRY_ATTEMPTS=1, CONNECTOR_RETRY_BACKOFF_SECONDS=0, CONNECTOR_CIRCUIT_FAILURE_THRESHOLD=1, CONNECTOR_CIRCUIT_OPEN_SECONDS=60)
    @patch("core.integration_resilience.requests.get")
    def test_circuit_opens_after_threshold(self, request):
        request.side_effect = __import__("requests").RequestException("down")
        with self.assertRaises(__import__("requests").RequestException):
            resilient_request("unit-circuit", "GET", "https://example.test")
        with self.assertRaises(ConnectorCircuitOpen):
            resilient_request("unit-circuit", "GET", "https://example.test")
