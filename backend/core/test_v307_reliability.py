from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import DataSyncRun
from .observability import redact
from .reliability import readiness_payload, sync_freshness
from .version import VERSION as FORGEGOV_VERSION


class ReliabilityV307Tests(SimpleTestCase):
    @patch("core.reliability.cache_health", return_value={"status": "healthy", "latency_ms": 1.0})
    @patch("core.reliability.database_health", return_value={"status": "healthy", "latency_ms": 2.0})
    def test_readiness_payload_is_ready_when_critical_dependencies_are_healthy(self, database, cache):
        payload = readiness_payload()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["version"], FORGEGOV_VERSION)

    @patch("core.views.readiness_payload", return_value={
        "status": "not_ready", "service": "forgegov-api", "product": "ForgeGov", "version": FORGEGOV_VERSION,
        "checks": {"database": {"status": "unavailable"}, "cache": {"status": "healthy"}},
    })
    def test_ready_endpoint_returns_503_when_dependency_is_down(self, payload):
        response = APIClient().get("/api/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")

    @patch("core.views.readiness_payload", return_value={
        "status": "ready", "service": "forgegov-api", "product": "ForgeGov", "version": FORGEGOV_VERSION,
        "checks": {"database": {"status": "healthy"}, "cache": {"status": "healthy"}},
    })
    def test_ready_endpoint_returns_200_when_dependencies_are_healthy(self, payload):
        response = APIClient().get("/api/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], FORGEGOV_VERSION)
        self.assertTrue(response["X-Request-ID"])

    def test_log_redaction_masks_common_credentials(self):
        value = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact(value)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", result)


class ReliabilityDatabaseV307Tests(TestCase):
    @override_settings(RELIABILITY_SYNC_STALE_HOURS=30, RELIABILITY_SYNC_SOURCES=("sam.gov",))
    def test_sync_freshness_marks_old_successful_run_stale(self):
        run = DataSyncRun.objects.create(source="sam.gov", status=DataSyncRun.Status.SUCCESS)
        run.finished_at = timezone.now() - timedelta(hours=31)
        run.save(update_fields=["finished_at", "updated_at"])
        payload = sync_freshness()
        self.assertEqual(payload["sources"]["sam.gov"]["status"], "stale")


class PlatformSystemReliabilityV307Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="v307-admin@example.com",
            email="v307-admin@example.com",
            password="StrongPass!234567",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("core.intelligence.services.award_ingestion.connector_registry_payload", return_value={"connectors": []})
    @patch("core.intelligence.services.connectors.connector_health", return_value={"connectors": [], "summary": {"total": 0, "healthy": 0, "attention": 0}})
    @patch("core.reliability.operational_health", return_value={"status": "ready", "version": FORGEGOV_VERSION})
    def test_platform_system_includes_operational_health(self, operations, connectors, registry):
        response = self.client.get("/api/platform-admin/system/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operations"]["version"], FORGEGOV_VERSION)
