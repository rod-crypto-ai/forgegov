from unittest.mock import Mock, patch

import requests
from django.test import override_settings

from .integrations import (
    _build_sam_params,
    search_federal_forecast_sources,
    search_grants_opportunities,
    search_sam_opportunities,
    search_state_local_sources,
    search_usaspending_contract_vehicles,
)
from .intelligence.connectors import get_connector
from .models import ConnectorSource, SavedSearch
from .tests import AuthenticatedApiTestCase


class OpportunityDiscoveryV323Tests(AuthenticatedApiTestCase):
    expected_connector_keys = {
        "sam-opportunities",
        "grants-opportunities",
        "sba-subnet",
        "federal-forecasts",
        "usaspending-awards",
        "usaspending-vehicles",
        "state-local-directory",
        "live-web-search",
    }

    def test_connector_endpoints_use_one_canonical_catalog(self):
        registry = self.client.get("/api/intelligence/connector-registry/").json()
        health = self.client.get("/api/intelligence/connectors/").json()
        registry_keys = {row["key"] for row in registry["connectors"]}
        health_keys = {row["key"] for row in health["connectors"]}
        self.assertEqual(registry_keys, self.expected_connector_keys)
        self.assertEqual(health_keys, self.expected_connector_keys)
        self.assertNotIn("texas-smartbuy-reference", registry_keys)

    def test_unprobed_catalog_never_claims_live_health(self):
        payload = self.client.get("/api/intelligence/connector-registry/").json()
        self.assertTrue(all(row["status"] == "not_verified" for row in payload["connectors"]))
        self.assertTrue(all(row["reachable"] is None for row in payload["connectors"]))
        self.assertEqual(payload["summary"]["healthy"], 0)
        self.assertEqual(payload["summary"]["verified"], 0)

    @override_settings(
        SAM_GOV_API_KEY="configured",
        SEARXNG_URL="http://searxng.internal",
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    @patch("core.intelligence.connectors.usaspending.usaspending_status", return_value={"reachable": True, "detail": "ok"})
    @patch("core.intelligence.connectors.reference.RegisteredSourceConnector._probe", return_value=("healthy", True, "verified"))
    def test_probe_summary_counts_only_observed_results(self, _probe, _usa):
        payload = self.client.get("/api/intelligence/connector-registry/?probe=true").json()
        state_local = next(row for row in payload["connectors"] if row["key"] == "state-local-directory")
        self.assertEqual(state_local["status"], "reference_only")
        self.assertIsNone(state_local["reachable"])
        self.assertEqual(payload["summary"]["healthy"], 7)
        self.assertEqual(payload["summary"]["verified"], 7)
        self.assertEqual(payload["summary"]["assessed"], len(self.expected_connector_keys))
        self.assertEqual(payload["summary"]["reference_only"], 1)
        self.assertEqual(payload["summary"]["attention"], 0)
        self.assertEqual(
            ConnectorSource.objects.filter(last_checked_at__isnull=False).count(),
            len(self.expected_connector_keys),
        )

    @override_settings(SAM_GOV_API_KEY="do-not-expose-this-key")
    @patch("core.integrations.search_sam_opportunities", side_effect=RuntimeError("do-not-expose-this-key"))
    def test_probe_failure_does_not_expose_credentials_or_exception_text(self, _search):
        health = get_connector("sam-opportunities").health(probe=True)
        self.assertEqual(health["status"], "unavailable")
        self.assertFalse(health["reachable"])
        self.assertNotIn("do-not-expose-this-key", health["detail"])

    @patch("core.integrations.resilient_request", side_effect=requests.RequestException("offline"))
    def test_forecast_failure_is_labeled_as_fallback_not_live(self, _request):
        payload = search_federal_forecast_sources()
        self.assertEqual(payload["status"], "fallback")
        self.assertFalse(payload["reachable"])
        self.assertTrue(payload["warning"])
        self.assertEqual(payload["total_records"], 1)

    def test_state_local_results_are_explicitly_directory_only(self):
        payload = search_state_local_sources(state="TX")
        self.assertEqual(payload["status"], "reference_only")
        self.assertIsNone(payload["reachable"])
        self.assertIn("not a live aggregated", payload["warning"])
        self.assertEqual([row["state"] for row in payload["results"]], ["TX"])

    @patch("core.integrations.resilient_request")
    def test_vehicle_search_has_normalized_pagination_contract(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {
            "results": [{"Award ID": "IDV-1", "Description": "Logistics vehicle"}],
            "page_metadata": {"hasNext": True},
        }
        request.return_value = response
        payload = search_usaspending_contract_vehicles(page=3, limit=50)
        self.assertEqual(payload["page"], 3)
        self.assertEqual(payload["limit"], 50)
        self.assertTrue(payload["has_next"])

    def test_sam_response_deadline_filters_use_official_date_format(self):
        params = _build_sam_params(response_from="2026-09-01", response_to="09/30/2026")
        self.assertEqual(params["rdlfrom"], "09/01/2026")
        self.assertEqual(params["rdlto"], "09/30/2026")

    @patch("core.tasks.search_sam_opportunities", return_value={"opportunities": []})
    def test_saved_sam_search_replays_all_discovery_filters(self, search):
        from .tasks import evaluate_saved_search_alerts

        SavedSearch.objects.create(
            organization=self.organization,
            owner=self.user,
            name="Full SAM filter",
            filters={
                "source": "sam.gov",
                "q": "logistics",
                "agency": "Department of Defense",
                "naics": "541512",
                "psc": "DA10",
                "state": "VA",
                "solnum": "W91TEST",
                "set_aside": "SBA",
                "ptype": "o",
                "posted_from": "2026-08-01",
                "posted_to": "2026-09-01",
                "response_from": "2026-09-15",
                "response_to": "2026-10-15",
                "status": "active",
            },
        )

        evaluate_saved_search_alerts.run(organization_id=self.organization.id)

        search.assert_called_once_with(
            keyword="logistics",
            agency="Department of Defense",
            naics="541512",
            psc="DA10",
            state="VA",
            solicitation_number="W91TEST",
            set_aside="SBA",
            procurement_type="o",
            posted_from="2026-08-01",
            posted_to="2026-09-01",
            response_from="2026-09-15",
            response_to="2026-10-15",
            opportunity_status="active",
            limit=50,
            persist=True,
        )

    @patch("core.tasks.search_grants_opportunities", return_value={"opportunities": []})
    def test_saved_grants_search_replays_sort_and_facets(self, search):
        from .tasks import evaluate_saved_search_alerts

        SavedSearch.objects.create(
            organization=self.organization,
            owner=self.user,
            name="Full Grants filter",
            filters={
                "source": "grants.gov",
                "q": "resilience",
                "opportunity_number": "EPA-TEST",
                "agency": "EPA",
                "statuses": "posted",
                "aln": "66.123",
                "funding_categories": "ENV",
                "eligibilities": "12",
                "funding_instruments": "CA",
                "sort_by": "closeDate|asc",
            },
        )

        evaluate_saved_search_alerts.run(organization_id=self.organization.id)

        search.assert_called_once_with(
            keyword="resilience",
            opportunity_number="EPA-TEST",
            agencies="EPA",
            statuses="posted",
            aln="66.123",
            funding_categories="ENV",
            eligibilities="12",
            funding_instruments="CA",
            sort_by="closeDate|asc",
            limit=50,
            persist=True,
        )

    @override_settings(SAM_GOV_API_KEY="configured")
    @patch("core.integrations.resilient_request")
    def test_sam_live_page_deduplicates_notice_ids_and_reports_provenance(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {
            "totalRecords": 2,
            "limit": 25,
            "offset": 0,
            "opportunitiesData": [
                {"noticeId": "same", "title": "First"},
                {"noticeId": "same", "title": "Duplicate"},
            ],
        }
        request.return_value = response
        payload = search_sam_opportunities()
        self.assertEqual([row["source_id"] for row in payload["opportunities"]], ["same"])
        self.assertEqual(payload["duplicate_records_removed"], 1)
        self.assertEqual(payload["opportunities"][0]["source_status"], "live")
        self.assertTrue(payload["opportunities"][0]["retrieved_at"])

    @patch("core.integrations.resilient_request")
    def test_grants_live_page_deduplicates_opportunity_ids(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {
            "errorcode": 0,
            "data": {
                "hitCount": 2,
                "oppHits": [
                    {"id": 321, "title": "First"},
                    {"id": 321, "title": "Duplicate"},
                ],
            },
        }
        request.return_value = response
        payload = search_grants_opportunities()
        self.assertEqual([row["source_id"] for row in payload["opportunities"]], ["grants.gov:321"])
        self.assertEqual(payload["duplicate_records_removed"], 1)
