from unittest.mock import Mock, patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .integrations import (
    _build_sam_params,
    fetch_grants_opportunity,
    fetch_sam_opportunity_documents,
    fetch_sam_opportunity_detail,
    search_sam_contract_awards,
    search_sam_subawards,
    search_sba_subnet_opportunities,
    search_federal_forecast_sources,
    search_usaspending_contract_vehicles,
    search_sam_opportunities,
    search_grants_opportunities,
    upsert_sam_opportunity,
)
from .ai import live_web_status
from .models import Award, IntelligenceAlert, Invitation, Membership, Opportunity, Organization, PipelineItem, SavedSearch, Vendor, ProjectRoom, ProjectRoomPartner, ProjectRoomTask, ProjectRoomNote, ProjectRoomFile, OrganizationProfile, NetworkConnection, ProjectRoomInvitation

User = get_user_model()


class AuthenticatedApiTestCase(TestCase):
    role = Membership.Role.OWNER

    def setUp(self):
        self.user = User.objects.create_user(username="owner@example.com", email="owner@example.com", password="StrongPass!234")
        self.organization = Organization.objects.create(name="Test Workspace", slug="test-workspace")
        Membership.objects.create(user=self.user, organization=self.organization, role=self.role)
        self.client = APIClient()
        self.client.force_authenticate(self.user)


class InvitationSecurityTests(AuthenticatedApiTestCase):
    def test_owner_role_cannot_be_invited(self):
        response = self.client.post(
            "/api/team/invitations/",
            {"email": "new-owner@example.com", "role": Membership.Role.OWNER},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_accepted_invitation_does_not_block_new_pending_invitation(self):
        Invitation.objects.create(
            organization=self.organization,
            email="repeat@example.com",
            role=Membership.Role.VIEWER,
            token="accepted-token",
            status=Invitation.Status.ACCEPTED,
            expires_at=timezone.now() + timedelta(days=1),
        )
        pending = Invitation.objects.create(
            organization=self.organization,
            email="repeat@example.com",
            role=Membership.Role.VIEWER,
            token="pending-token",
            status=Invitation.Status.PENDING,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(pending.status, Invitation.Status.PENDING)


class HealthTests(TestCase):
    def test_health_endpoint(self):
        response = APIClient().get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["product"], "ForgeGov")
        self.assertEqual(response.json()["version"], "2.4.0")

    @override_settings(ALLOWED_HOSTS=["forgegov-api.onrender.com"])
    def test_render_health_check_survives_custom_domain_host_transition(self):
        response = APIClient().get("/api/health/", HTTP_HOST="api.example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "2.4.0")


class RouterRegressionTests(TestCase):
    def test_router_names_are_registered(self):
        self.assertEqual(reverse("organization-list"), "/api/organizations/")
        self.assertEqual(reverse("pipeline-item-list"), "/api/pipeline/")
        self.assertEqual(reverse("task-list"), "/api/tasks/")
        self.assertEqual(reverse("saved-search-list"), "/api/saved-searches/")
        self.assertEqual(reverse("contact-group-list"), "/api/contact-groups/")
        self.assertEqual(reverse("intelligence-alert-list"), "/api/alerts/")


class OpportunityTests(AuthenticatedApiTestCase):
    def test_search(self):
        Opportunity.objects.create(source_id="x-1", title="Vehicle maintenance support", agency="USMC")
        Opportunity.objects.create(source_id="x-2", title="Custodial services", agency="GSA")
        response = self.client.get("/api/opportunities/?search=vehicle")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_dashboard_summary_uses_database_counts(self):
        Opportunity.objects.create(source_id="x-1", title="Active", active=True)
        Opportunity.objects.create(source_id="x-2", title="Archived", active=False)
        response = self.client.get("/api/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["opportunities"], {"total": 2, "active": 1})

    def test_shared_opportunity_catalog_is_read_only(self):
        response = self.client.post("/api/opportunities/", {"source_id": "unsafe", "title": "Unsafe write"}, format="json")
        self.assertEqual(response.status_code, 405)


class WorkspacePermissionTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="viewer@example.com", email="viewer@example.com", password="StrongPass!234")
        self.contributor = User.objects.create_user(username="contributor@example.com", email="contributor@example.com", password="StrongPass!234")
        self.other = User.objects.create_user(username="other@example.com", email="other@example.com", password="StrongPass!234")
        self.org = Organization.objects.create(name="Org A", slug="org-a")
        self.other_org = Organization.objects.create(name="Org B", slug="org-b")
        Membership.objects.create(user=self.viewer, organization=self.org, role=Membership.Role.VIEWER)
        Membership.objects.create(user=self.contributor, organization=self.org, role=Membership.Role.CAPTURE)
        Membership.objects.create(user=self.other, organization=self.other_org, role=Membership.Role.OWNER)

    def test_viewer_cannot_create_workspace_task(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        response = client.post("/api/workflow/tasks/", {"title": "Unauthorized task"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_task_cannot_link_pipeline_from_other_workspace(self):
        opportunity = Opportunity.objects.create(source_id="cross-tenant", title="Cross tenant")
        foreign_pipeline = PipelineItem.objects.create(organization=self.other_org, opportunity=opportunity, owner=self.other)
        client = APIClient()
        client.force_authenticate(self.contributor)
        response = client.post("/api/workflow/tasks/", {"title": "Bad link", "pipeline_item": foreign_pipeline.id}, format="json")
        self.assertEqual(response.status_code, 400)


class SamIntegrationTests(TestCase):
    def test_sam_date_filters_are_normalized(self):
        params = _build_sam_params(posted_from="2026-07-01", posted_to="07/26/2026")
        self.assertEqual(params["postedFrom"], "07/01/2026")
        self.assertEqual(params["postedTo"], "07/26/2026")

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
            "totalRecords": "1",
            "limit": "25",
            "offset": "0",
            "opportunitiesData": [{"noticeId": "abc-123", "title": "Vehicle maintenance"}],
        }
        mock_get.return_value = response

        result = search_sam_opportunities(keyword="vehicle", persist=True)

        self.assertEqual(result["persisted"]["created"], 1)
        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["limit"], 25)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["opportunities"][0]["source_url"], "https://sam.gov/opp/abc-123/view")
        self.assertTrue(Opportunity.objects.filter(source_id="abc-123").exists())
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["title"], "vehicle")
        self.assertNotIn("q", called_params)


    @override_settings(SAM_GOV_API_KEY="test-key")
    @patch("core.integrations.requests.get")
    def test_sam_404_is_an_empty_result_set(self, mock_get):
        response = Mock()
        response.ok = False
        response.status_code = 404
        mock_get.return_value = response

        result = search_sam_opportunities(keyword="no-match")

        self.assertEqual(result["total_records"], 0)
        self.assertEqual(result["opportunities"], [])


class SamContractAwardsIntegrationTests(TestCase):
    @override_settings(SAM_GOV_API_KEY="test-key", SAM_CONTRACT_AWARDS_BASE_URL="https://api.sam.gov/contract-awards/v1/search")
    @patch("core.integrations.requests.get")
    def test_contract_awards_are_normalized(self, mock_get):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "totalRecords": "1",
            "awardSummary": [{
                "contractId": {"piid": "W56HZV26C0001", "modificationNumber": "0", "referencedIDVPiid": "W56HZV20D0001"},
                "coreData": {
                    "awardOrIDV": "AWARD",
                    "awardOrIDVType": {"name": "DELIVERY ORDER"},
                    "title": "JLTV maintenance support",
                    "federalOrganization": {"contractingInformation": {"contractingDepartment": {"name": "DEPT OF DEFENSE"}}},
                },
                "awardDetails": {
                    "dollarsObligated": 125000,
                    "totalDollarsObligated": 500000,
                    "awardeeData": {"awardeeHeader": {"awardeeName": "HOWARD DYNAMICS LLC"}},
                },
            }],
        }
        mock_get.return_value = response

        result = search_sam_contract_awards(record_type="contracts", keyword="JLTV", limit=1)

        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["results"][0]["piid"], "W56HZV26C0001")
        self.assertEqual(result["results"][0]["recipient_name"], "HOWARD DYNAMICS LLC")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["awardOrIDV"], "Award")
        self.assertEqual(params["q"], "JLTV")

    @override_settings(SAM_GOV_API_KEY="test-key")
    @patch("core.integrations.requests.get")
    def test_opportunity_documents_include_description_and_links(self, mock_get):
        Opportunity.objects.create(
            source_id="notice-123",
            title="Document test",
            description="Fallback",
            source_url="https://sam.gov/opp/notice-123/view",
            resource_links=["https://example.gov/pws.pdf"],
            raw_data={"description": "https://api.sam.gov/description/notice-123"},
        )
        response = Mock()
        response.ok = True
        response.json.return_value = {"description": "Live description"}
        mock_get.return_value = response

        result = fetch_sam_opportunity_documents("notice-123")

        self.assertEqual(result["description"], "Live description")
        self.assertEqual(result["documents"][0]["url"], "https://example.gov/pws.pdf")
        self.assertTrue(result["documents"][0]["preview_available"])


class UsaSpendingIntegrationTests(AuthenticatedApiTestCase):
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
        api_response = self.client.get("/api/live/usaspending/awards/?q=logistics")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["results"], [])


class OpenAIIntegrationTests(AuthenticatedApiTestCase):
    @override_settings(OPENAI_API_KEY="")
    def test_missing_openai_key_returns_configuration_error(self):
        response = self.client.post("/api/ai/chat/", {"message": "Review my pipeline"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])

    @override_settings(
        OPENAI_API_KEY="test-openai-key",
        OPENAI_MODEL="gpt-5-mini",
        OPENAI_API_BASE_URL="https://api.openai.com/v1",
        OPENAI_TIMEOUT_SECONDS=10,
        OPENAI_MAX_OUTPUT_TOKENS=500,
    )
    @patch("core.ai.requests.post")
    def test_ai_chat_calls_responses_api_and_returns_grounded_answer(self, mock_post):
        Opportunity.objects.create(
            source_id="ai-opp-1",
            title="Vehicle maintenance support",
            agency="USMC",
            source_url="https://sam.gov/opp/ai-opp-1/view",
            active=True,
        )
        upstream = Mock()
        upstream.ok = True
        upstream.status_code = 200
        upstream.headers = {"x-request-id": "req_test"}
        upstream.json.return_value = {
            "id": "resp_test",
            "model": "gpt-5-mini",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "Review the maintenance opportunity [OPP-1]."}],
            }],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        mock_post.return_value = upstream

        response = self.client.post("/api/ai/chat/", {"message": "What should I review?", "history": []}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model"], "gpt-5-mini")
        self.assertIn("[OPP-1]", response.json()["answer"])
        request_kwargs = mock_post.call_args.kwargs
        self.assertEqual(request_kwargs["headers"]["Authorization"], "Bearer test-openai-key")
        self.assertTrue(request_kwargs["json"]["store"] is False)
        self.assertIn("Vehicle maintenance support", request_kwargs["json"]["input"])

    @override_settings(
        OPENAI_API_KEY="test-openai-key",
        OPENAI_MODEL="gpt-5-mini",
        OPENAI_API_BASE_URL="https://api.openai.com/v1",
        OPENAI_TIMEOUT_SECONDS=10,
        OPENAI_MAX_OUTPUT_TOKENS=500,
    )
    @patch("core.ai.requests.post")
    def test_ai_context_does_not_include_other_workspace_tasks(self, mock_post):
        other_user = User.objects.create_user(username="other-ai@example.com", password="StrongPass!234")
        other_org = Organization.objects.create(name="Other AI Org", slug="other-ai-org")
        Membership.objects.create(user=other_user, organization=other_org, role=Membership.Role.OWNER)
        from .models import Task
        Task.objects.create(organization=self.organization, title="Visible task")
        Task.objects.create(organization=other_org, title="Secret foreign task")

        upstream = Mock()
        upstream.ok = True
        upstream.status_code = 200
        upstream.headers = {}
        upstream.json.return_value = {
            "id": "resp_test",
            "model": "gpt-5-mini",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Done [TASK-1]."}]}],
        }
        mock_post.return_value = upstream

        response = self.client.post("/api/ai/chat/", {"message": "Review tasks"}, format="json")
        self.assertEqual(response.status_code, 200)
        sent_input = mock_post.call_args.kwargs["json"]["input"]
        self.assertIn("Visible task", sent_input)
        self.assertNotIn("Secret foreign task", sent_input)


class ExpansionIntegrationTests(AuthenticatedApiTestCase):
    @patch("core.integrations.requests.post")
    def test_contract_vehicle_search_persists_vehicle_award(self, mock_post):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "page_metadata": {"page": 1, "hasNext": False},
            "results": [{
                "Award ID": "GS00Q14OADU428",
                "generated_unique_award_id": "CONT_IDV_GS00Q14OADU428_4732",
                "Recipient Name": "EXAMPLE PRIME LLC",
                "Award Amount": 1000000,
                "Potential Award Amount": 25000000,
                "Description": "Governmentwide acquisition contract",
                "Start Date": "2024-01-01",
                "End Date": "2029-12-31",
                "Awarding Agency": "General Services Administration",
            }],
        }
        mock_post.return_value = response

        result = search_usaspending_contract_vehicles(keyword="acquisition", persist=True)

        self.assertEqual(result["persisted"]["created"], 1)
        award = Award.objects.get(source_id="CONT_IDV_GS00Q14OADU428_4732")
        self.assertEqual(award.award_type, Award.AwardType.VEHICLE)
        codes = mock_post.call_args.kwargs["json"]["filters"]["award_type_codes"]
        self.assertIn("IDV_A", codes)

    @patch("core.integrations.requests.get")
    def test_forecast_directory_parses_official_agency_links(self, mock_get):
        response = Mock()
        response.text = """
            <table><tbody><tr>
              <td><a href='https://agency.gov'>Department of Testing</a></td>
              <td><a href='https://agency.gov/forecast'>Agency Procurement Forecast</a></td>
            </tr></tbody></table>
        """
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = search_federal_forecast_sources(query="testing")

        self.assertTrue(result["reachable"])
        self.assertEqual(result["results"][0]["agency"], "Department of Testing")
        self.assertEqual(result["results"][0]["forecast_url"], "https://agency.gov/forecast")

    @override_settings(SAM_GOV_API_KEY="test-key", SAM_SUBAWARDS_BASE_URL="https://api.sam.gov/prod/contract/v1/subcontracts/search")
    @patch("core.integrations.requests.get")
    def test_subaward_search_normalizes_records(self, mock_get):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "totalRecords": 1,
            "totalPages": 1,
            "pageNumber": 0,
            "data": [{
                "piid": "W91QVN20F0157",
                "referencedIDVPIID": "W52P1J18DA075",
                "primeEntityName": "PRIME LLC",
                "primeEntityUei": "PRIMEUEI123",
                "subEntityLegalBusinessName": "SMALL BUSINESS LLC",
                "subEntityUei": "SUBUEI456",
                "subAwardAmount": 325000,
                "subAwardDescription": "Vehicle maintenance",
                "subAwardDate": "2026-01-10",
                "subContractorNaics": {"code": "811111", "description": "Automotive Mechanical and Electrical Repair"},
                "entityPhysicalAddress": {"city": "Killeen", "state": {"code": "TX", "name": "Texas"}},
                "subEntityBusinessTypes": ["Small Business"],
            }],
        }
        mock_get.return_value = response

        result = search_sam_subawards(referenced_idv="W52P1J18DA075")

        self.assertEqual(result["total_records"], 1)
        record = result["results"][0]
        self.assertEqual(record["prime_contractor"], "PRIME LLC")
        self.assertEqual(record["subcontractor"], "SMALL BUSINESS LLC")
        self.assertEqual(record["action_date"], "2026-01-10")
        self.assertEqual(record["naics"], "811111")
        self.assertEqual(record["place_of_performance"], "Killeen, TX")
        self.assertEqual(record["sub_entity_uei"], "SUBUEI456")
        self.assertEqual(mock_get.call_args.kwargs["params"]["referencedIDVPIID"], "W52P1J18DA075")

    @override_settings(SBA_SUBNET_URL="https://legacy.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities", SBA_SUBNET_FALLBACK_URL="")
    @patch("core.integrations.requests.get")
    def test_sba_subnet_parser_separates_title_and_description(self, mock_get):
        response = Mock()
        response.url = "https://legacy.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities"
        response.text = """
            <table><tbody><tr>
              <td><a href='/subnet/opportunity/123'>JLTV Maintenance Support</a> Regional field maintenance subcontract</td>
              <td>08/31/2026</td><td>10/01/2026</td><td>Fort Hood, TX</td><td>811310</td><td>Jane Doe</td>
            </tr></tbody></table>
        """
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = search_sba_subnet_opportunities(query="maintenance", state="TX")

        self.assertEqual(result["total_records"], 1)
        record = result["results"][0]
        self.assertEqual(record["title"], "JLTV Maintenance Support")
        self.assertEqual(record["description"], "Regional field maintenance subcontract")
        self.assertEqual(record["source_url"], "https://legacy.sba.gov/subnet/opportunity/123")

    @override_settings(SAM_GOV_API_KEY="test-key")
    @patch("core.integrations.requests.get")
    def test_opportunity_detail_combines_record_and_documents(self, mock_get):
        search_response = Mock()
        search_response.ok = True
        search_response.status_code = 200
        search_response.json.return_value = {
            "totalRecords": 1,
            "limit": 1,
            "offset": 0,
            "opportunitiesData": [{
                "noticeId": "detail-123",
                "title": "Detail opportunity",
                "fullParentPathName": "Department of Testing",
                "naicsCode": "811310",
                "resourceLinks": ["https://example.gov/pws.pdf"],
            }],
        }
        mock_get.return_value = search_response
        Award.objects.create(
            source_id="incumbent-award-1",
            award_number="N00000-25-C-0001",
            recipient_name="EXAMPLE INCUMBENT LLC",
            awarding_agency="Department of Testing",
            naics_code="811310",
            obligated_amount=1250000,
        )

        result = fetch_sam_opportunity_detail("detail-123")

        self.assertEqual(result["opportunity"]["noticeId"], "detail-123")
        self.assertEqual(result["documents"][0]["name"], "Attachment 1")
        self.assertIn("not confirmed incumbents", result["incumbent_signal_note"])
        self.assertEqual(result["incumbent_signals"][0]["recipient_name"], "EXAMPLE INCUMBENT LLC")


class IntelligenceAlertTests(AuthenticatedApiTestCase):
    @patch("core.tasks.search_sam_opportunities")
    def test_saved_search_evaluation_creates_deduplicated_alert(self, mock_search):
        from .tasks import evaluate_saved_search_alerts

        saved = SavedSearch.objects.create(
            organization=self.organization,
            owner=self.user,
            name="Maintenance",
            filters={"source": "sam.gov", "q": "maintenance"},
        )
        mock_search.return_value = {
            "opportunities": [{
                "source_id": "alert-opp-1",
                "noticeId": "alert-opp-1",
                "title": "Maintenance requirement",
                "source_url": "https://sam.gov/opp/alert-opp-1/view",
            }],
        }
        Opportunity.objects.create(source_id="alert-opp-1", title="Maintenance requirement")

        first = evaluate_saved_search_alerts.run()
        second = evaluate_saved_search_alerts.run()

        self.assertEqual(first["alerts_created"], 1)
        self.assertEqual(second["alerts_created"], 0)
        alert = IntelligenceAlert.objects.get(saved_search=saved)
        self.assertEqual(alert.organization, self.organization)
        self.assertFalse(alert.read)

    @patch("core.tasks.evaluate_saved_search_alerts.run")
    def test_manual_alert_evaluation_is_scoped_to_current_workspace(self, mock_run):
        mock_run.return_value = {"saved_searches_evaluated": 0, "alerts_created": 0}

        response = self.client.post("/api/workflow/saved-searches/evaluate/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        mock_run.assert_called_once_with(organization_id=self.organization.id)

    def test_alert_patch_only_changes_read_and_dismissed_state(self):
        alert = IntelligenceAlert.objects.create(organization=self.organization, title="Original", source_id="patch-1")

        response = self.client.patch(
            f"/api/alerts/{alert.id}/",
            {"title": "Tampered", "read": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.title, "Original")
        self.assertTrue(alert.read)

    def test_alerts_are_organization_scoped(self):
        other_user = User.objects.create_user(username="other-alert@example.com", email="other-alert@example.com", password="StrongPass!234")
        other_org = Organization.objects.create(name="Other Alerts", slug="other-alerts")
        Membership.objects.create(user=other_user, organization=other_org, role=Membership.Role.OWNER)
        IntelligenceAlert.objects.create(organization=other_org, title="Other alert", source_id="other-1")
        IntelligenceAlert.objects.create(organization=self.organization, title="My alert", source_id="mine-1")

        response = self.client.get("/api/alerts/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["title"], "My alert")


class PartnerDiscoveryTests(AuthenticatedApiTestCase):
    def test_partner_discovery_filters_portably_and_returns_award_signals(self):
        Vendor.objects.create(
            name="HOWARD PARTNER LLC",
            uei="UEI123",
            state="TX",
            naics_codes=["811310"],
            socioeconomic_statuses=["SDVOSB"],
        )
        Vendor.objects.create(name="OTHER VENDOR LLC", state="VA", naics_codes=["541512"])
        Award.objects.create(
            source_id="partner-award-1",
            recipient_name="HOWARD PARTNER LLC",
            awarding_agency="Department of the Army",
            obligated_amount=750000,
        )

        response = self.client.get("/api/intelligence/partners/?naics=811310&state=TX&status=SDVOSB")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_records"], 1)
        self.assertEqual(response.json()["results"][0]["name"], "HOWARD PARTNER LLC")
        self.assertEqual(response.json()["results"][0]["award_count"], 1)


class GrantsIntegrationTests(AuthenticatedApiTestCase):
    @override_settings(GRANTS_GOV_BASE_URL="https://api.grants.gov/v1/api")
    @patch("core.integrations.requests.post")
    def test_grants_search_normalizes_and_persists_internal_route(self, mock_post):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "errorcode": 0,
            "data": {
                "hitCount": 1,
                "startRecord": 0,
                "searchParams": {"rows": 25},
                "oppHits": [{
                    "id": 98765,
                    "number": "FG-2026-001",
                    "title": "Resilient Infrastructure Grant",
                    "agencyName": "Department of Testing",
                    "oppStatus": "posted",
                    "openDate": "07/01/2026",
                    "closeDate": "08/31/2026",
                    "alnist": [{"alnNumber": "20.999"}],
                }],
            },
        }
        mock_post.return_value = response

        result = search_grants_opportunities(keyword="infrastructure", persist=True)

        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["opportunities"][0]["source_id"], "grants.gov:98765")
        self.assertEqual(result["opportunities"][0]["source_url"], "https://www.grants.gov/search-results-detail/98765")
        self.assertTrue(Opportunity.objects.filter(source_id="grants.gov:98765", source="grants.gov").exists())

    @override_settings(GRANTS_GOV_BASE_URL="https://api.grants.gov/v1/api")
    @patch("core.integrations.requests.post")
    def test_grant_detail_returns_workspace_fields_and_documents(self, mock_post):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "errorcode": 0,
            "data": {
                "id": 98765,
                "opportunityTitle": "Resilient Infrastructure Grant",
                "opportunityNumber": "FG-2026-001",
                "owningAgencyCode": "DOT",
                "oppStatus": "posted",
                "agencyDetails": {"agencyName": "Department of Transportation", "agencyCode": "DOT"},
                "synopsis": {
                    "postingDate": "07/01/2026",
                    "responseDateDesc": "08/31/2026",
                    "synopsisDesc": "Funds resilient public infrastructure projects.",
                    "awardCeiling": 5000000,
                    "awardFloor": 250000,
                    "costSharing": "Yes",
                    "applicantTypes": [{"id": "01", "description": "State governments"}],
                    "fundingInstruments": [{"id": "G", "description": "Grant"}],
                    "agencyContactName": "Program Office",
                    "agencyContactEmail": "program@example.gov",
                },
                "alns": [{"alnNumber": "20.999", "programTitle": "Infrastructure Program"}],
                "synopsisAttachmentFolders": [{
                    "folderName": "Application package",
                    "synopsisAttachments": [{
                        "fileName": "NOFO.pdf",
                        "downloadUrl": "https://example.gov/NOFO.pdf",
                        "fileDescription": "Notice of funding opportunity",
                    }],
                }],
            },
        }
        mock_post.return_value = response

        result = fetch_grants_opportunity("grants.gov:98765", persist=True)

        self.assertEqual(result["opportunity"]["source_id"], "grants.gov:98765")
        self.assertEqual(result["documents"][0]["name"], "NOFO.pdf")
        self.assertEqual(result["eligibilities"][0]["label"], "State governments")
        self.assertEqual(result["contacts"][0]["email"], "program@example.gov")
        self.assertEqual(result["award_ceiling"], 5000000)

    def test_global_search_routes_grants_to_grant_workspace(self):
        Opportunity.objects.create(
            source_id="grants.gov:12345",
            source="grants.gov",
            title="Community resilience grant",
            agency="FEMA",
        )
        response = self.client.get("/api/intelligence/search/?q=resilience")
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["type"], "grant")
        self.assertEqual(result["href"], "/opportunities/federal-grants/12345")


class LiveWebIntegrationTests(TestCase):
    def tearDown(self):
        cache.clear()

    @override_settings(SEARXNG_URL="http://searxng:8080", AI_WEB_SEARCH_ENABLED=True)
    @patch("core.ai.requests.get")
    def test_live_web_status_probes_json_search(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": [{"title": "Official source", "url": "https://example.gov", "content": "Current information"}]}
        mock_get.return_value = response

        result = live_web_status(probe=True)

        self.assertTrue(result["configured"])
        self.assertTrue(result["reachable"])
        self.assertEqual(result["status"], "live")
        self.assertEqual(mock_get.call_args.kwargs["params"]["format"], "json")

    @override_settings(SEARXNG_URL="http://searxng:8080", AI_WEB_SEARCH_ENABLED=True)
    @patch("core.ai.requests.get", side_effect=__import__("requests").RequestException("offline"))
    def test_live_web_status_reports_reconnecting_without_false_live_claim(self, _mock_get):
        result = live_web_status(probe=True)
        self.assertTrue(result["configured"])
        self.assertFalse(result["reachable"])
        self.assertEqual(result["status"], "unavailable")


class SubnetFallbackTests(TestCase):
    def tearDown(self):
        cache.clear()

    @override_settings(
        SBA_SUBNET_URL="https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
        SBA_SUBNET_FALLBACK_URL="",
        SEARXNG_URL="",
    )
    @patch("core.integrations.requests.get")
    def test_subnet_prioritizes_current_official_listing_when_env_has_prior_url(self, mock_get):
        response = Mock()
        response.url = "https://legacy.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities"
        response.text = """
            <table><tbody><tr>
              <td><a href='/opportunity/current-1'>Current SBA opportunity</a> Prime Contractor Current requirement</td>
              <td>09/03/2026</td><td>10/12/2026</td><td>California</td><td>237310</td><td>Jane Doe</td>
            </tr></tbody></table>
        """
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = search_sba_subnet_opportunities()

        self.assertEqual(result["status"], "live")
        self.assertEqual(result["results"][0]["title"], "Current SBA opportunity")
        self.assertEqual(
            mock_get.call_args_list[0].args[0],
            "https://legacy.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
        )

    @override_settings(
        SBA_SUBNET_URL="https://www.sba.gov/subnet",
        SBA_SUBNET_FALLBACK_URL="",
        SEARXNG_URL="http://searxng:8080",
        AI_WEB_SEARCH_ENABLED=True,
    )
    @patch("core.integrations.requests.get")
    def test_subnet_uses_official_sba_index_when_direct_directory_reconnects(self, mock_get):
        def side_effect(url, **kwargs):
            if "searxng" in url:
                response = Mock()
                response.raise_for_status.return_value = None
                response.json.return_value = {"results": [{
                    "title": "Aerial Structures Rehab",
                    "url": "https://www.sba.gov/opportunity/aerial-structures-rehab",
                    "content": "Subcontracting opportunity in Washington, DC",
                }]}
                return response
            raise __import__("requests").RequestException("SBA connection reset")
        mock_get.side_effect = side_effect

        result = search_sba_subnet_opportunities(query="structures", state="DC")

        self.assertEqual(result["status"], "indexed")
        self.assertEqual(result["results"][0]["title"], "Aerial Structures Rehab")
        self.assertIn("sba.gov/opportunity/", result["results"][0]["source_url"])
        self.assertTrue(Opportunity.objects.filter(source="sba-subnet").exists())

    @override_settings(SBA_SUBNET_URL="https://www.sba.gov/subnet", SBA_SUBNET_FALLBACK_URL="", SEARXNG_URL="", AI_WEB_SEARCH_ENABLED=True)
    @patch("core.integrations.requests.get", side_effect=__import__("requests").RequestException("offline"))
    def test_subnet_returns_persisted_history_instead_of_dead_end(self, _mock_get):
        Opportunity.objects.create(
            source_id="sba-subnet:stored",
            source="sba-subnet",
            title="Stored subcontract opportunity",
            agency="Prime Contractor LLC",
            active=True,
            place_of_performance="Texas",
            raw_data={"closing_date": "08/31/2026", "naics": "811310"},
        )
        result = search_sba_subnet_opportunities(query="stored", state="Texas")
        self.assertEqual(result["status"], "cached")
        self.assertEqual(result["results"][0]["title"], "Stored subcontract opportunity")
        self.assertIn("verified", result["warning"].lower())


class GrantAlertEvaluationTests(AuthenticatedApiTestCase):
    @patch("core.tasks.search_grants_opportunities")
    def test_grants_saved_search_creates_internal_workspace_alert(self, mock_search):
        from .tasks import evaluate_saved_search_alerts

        saved = SavedSearch.objects.create(
            organization=self.organization,
            owner=self.user,
            name="Resilience grants",
            filters={"source": "grants.gov", "q": "resilience", "statuses": "posted"},
        )
        mock_search.return_value = {
            "opportunities": [{
                "source_id": "grants.gov:445566",
                "id": 445566,
                "title": "Community Resilience Grant",
                "agencyName": "FEMA",
                "source_url": "https://www.grants.gov/search-results-detail/445566",
            }],
        }
        opportunity = Opportunity.objects.create(
            source_id="grants.gov:445566",
            source="grants.gov",
            title="Community Resilience Grant",
            agency="FEMA",
        )

        result = evaluate_saved_search_alerts.run(organization_id=self.organization.id)

        self.assertEqual(result["alerts_created"], 1)
        alert = IntelligenceAlert.objects.get(saved_search=saved)
        self.assertEqual(alert.opportunity, opportunity)
        self.assertEqual(alert.source_id, "grants.gov:445566")
        self.assertEqual(alert.source_url, "https://www.grants.gov/search-results-detail/445566")
        mock_search.assert_called_once()

class DocumentIntelligenceUnitTests(SimpleTestCase):
    def test_text_extraction_and_chunking(self):
        from .document_intelligence import chunk_sections, extract_document
        sections = extract_document(b"Section L\nSubmit the technical volume by Friday.", "instructions.txt", "text/plain")
        chunks = list(chunk_sections(sections))
        self.assertEqual(len(chunks), 1)
        self.assertIn("technical volume", chunks[0][3])

    def test_private_document_urls_are_blocked(self):
        from .document_intelligence import DocumentIngestionError, _validate_public_url
        with self.assertRaises(DocumentIngestionError):
            _validate_public_url("http://127.0.0.1:8000/private")


class ProjectRoomCollaborationSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="room-owner@example.com", email="room-owner@example.com", password="StrongPass!234")
        self.partner_user = User.objects.create_user(username="partner@example.com", email="partner@example.com", password="StrongPass!234")
        self.outsider = User.objects.create_user(username="outsider@example.com", email="outsider@example.com", password="StrongPass!234")
        self.owner_org = Organization.objects.create(name="Prime Company", slug="prime-company")
        self.partner_org = Organization.objects.create(name="Partner Company", slug="partner-company")
        self.outsider_org = Organization.objects.create(name="Outside Company", slug="outside-company")
        Membership.objects.create(user=self.owner, organization=self.owner_org, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.partner_user, organization=self.partner_org, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.outsider, organization=self.outsider_org, role=Membership.Role.OWNER)
        self.room = ProjectRoom.objects.create(owner_organization=self.owner_org, name="Secure Pursuit", created_by=self.owner)
        ProjectRoomPartner.objects.create(project_room=self.room, organization=self.partner_org, can_upload=True, can_comment=True, can_view_pricing=False)
        self.internal_task = ProjectRoomTask.objects.create(project_room=self.room, title="Prime-only pricing review", visibility="internal", created_by=self.owner)
        self.shared_task = ProjectRoomTask.objects.create(project_room=self.room, title="Shared technical draft", visibility="shared", created_by=self.owner)
        ProjectRoomNote.objects.create(project_room=self.room, title="Internal strategy", visibility="internal", author=self.owner)
        ProjectRoomNote.objects.create(project_room=self.room, title="Shared minutes", visibility="shared", author=self.owner)
        ProjectRoomFile.objects.create(project_room=self.room, name="technical.pdf", url="https://example.com/technical.pdf", visibility="shared", uploaded_by=self.owner)
        ProjectRoomFile.objects.create(project_room=self.room, name="pricing.xlsx", url="https://example.com/pricing.xlsx", visibility="pricing", uploaded_by=self.owner)

    def client_for(self, user):
        client = APIClient(); client.force_authenticate(user); return client

    def test_partner_only_sees_shared_tasks_and_notes(self):
        client = self.client_for(self.partner_user)
        tasks = client.get(f"/api/project-rooms/{self.room.id}/tasks/")
        notes = client.get(f"/api/project-rooms/{self.room.id}/notes/")
        self.assertEqual(tasks.status_code, 200)
        self.assertEqual([row["title"] for row in tasks.json()], ["Shared technical draft"])
        self.assertEqual([row["title"] for row in notes.json()], ["Shared minutes"])

    def test_partner_without_pricing_permission_cannot_see_pricing_file(self):
        response = self.client_for(self.partner_user).get(f"/api/project-rooms/{self.room.id}/files/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["name"] for row in response.json()], ["technical.pdf"])

    def test_outsider_cannot_access_room_collaboration(self):
        response = self.client_for(self.outsider).get(f"/api/project-rooms/{self.room.id}/tasks/")
        self.assertEqual(response.status_code, 404)

    def test_partner_cannot_create_internal_task(self):
        response = self.client_for(self.partner_user).post(f"/api/project-rooms/{self.room.id}/tasks/", {"title":"Hidden task","visibility":"internal"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_owner_sees_internal_and_shared_records(self):
        response = self.client_for(self.owner).get(f"/api/project-rooms/{self.room.id}/tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["title"] for row in response.json()}, {"Prime-only pricing review", "Shared technical draft"})


class ForgeGovNetworkSecurityTests(TestCase):
    def setUp(self):
        self.prime_user = User.objects.create_user(username="prime-net@example.com", email="prime-net@example.com", password="StrongPass!234")
        self.partner_user = User.objects.create_user(username="partner-net@example.com", email="partner-net@example.com", password="StrongPass!234")
        self.outsider_user = User.objects.create_user(username="outsider-net@example.com", email="outsider-net@example.com", password="StrongPass!234")
        self.prime = Organization.objects.create(name="Network Prime", slug="network-prime")
        self.partner = Organization.objects.create(name="Network Partner", slug="network-partner")
        self.outsider = Organization.objects.create(name="Network Outsider", slug="network-outsider")
        Membership.objects.create(user=self.prime_user, organization=self.prime, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.partner_user, organization=self.partner, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.outsider_user, organization=self.outsider, role=Membership.Role.OWNER)
        OrganizationProfile.objects.create(organization=self.partner, tagline="Cyber and logistics", capabilities=["Cybersecurity", "Logistics"], certifications=["SDVOSB"])
        OrganizationProfile.objects.create(organization=self.outsider, tagline="Construction", capabilities=["Concrete"])
        self.room = ProjectRoom.objects.create(owner_organization=self.prime, name="Network Pursuit", created_by=self.prime_user)

    def client_for(self, user):
        client = APIClient(); client.force_authenticate(user); return client

    def test_directory_excludes_requesting_company_and_searches_capabilities(self):
        response = self.client_for(self.prime_user).get("/api/network/directory/?q=Cybersecurity")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["organization_name"] for row in response.json()["results"]], ["Network Partner"])

    def test_connection_requires_recipient_acceptance(self):
        created = self.client_for(self.prime_user).post("/api/network/connections/", {"recipient": self.partner.id}, format="json")
        self.assertEqual(created.status_code, 201)
        row = NetworkConnection.objects.get(pk=created.json()["id"])
        self.assertEqual(row.status, NetworkConnection.Status.PENDING)
        accepted = self.client_for(self.partner_user).post(f"/api/network/connections/{row.id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(accepted.status_code, 200)
        row.refresh_from_db(); self.assertEqual(row.status, NetworkConnection.Status.ACCEPTED)

    def test_unconnected_company_cannot_be_invited_to_room(self):
        response = self.client_for(self.prime_user).post("/api/network/project-room-invitations/", {"project_room": self.room.id, "invited_organization": self.partner.id}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_accepting_room_invitation_creates_scoped_partner_access(self):
        NetworkConnection.objects.create(requester=self.prime, recipient=self.partner, requested_by=self.prime_user, status=NetworkConnection.Status.ACCEPTED)
        invite = self.client_for(self.prime_user).post("/api/network/project-room-invitations/", {"project_room": self.room.id, "invited_organization": self.partner.id, "can_view_pricing": False}, format="json")
        self.assertEqual(invite.status_code, 201)
        accepted = self.client_for(self.partner_user).post(f"/api/network/project-room-invitations/{invite.json()['id']}/respond/", {"action":"accept"}, format="json")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(ProjectRoomPartner.objects.filter(project_room=self.room, organization=self.partner, can_view_pricing=False).exists())
        self.assertFalse(ProjectRoomPartner.objects.filter(project_room=self.room, organization=self.outsider).exists())
