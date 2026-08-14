from .models import OpportunityWorkspace
from unittest.mock import Mock, patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
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
from .capture_intelligence import build_capture_assessment
from .win_strategy import build_win_strategy
from .models import Award, IntelligenceAlert, Invitation, Membership, Opportunity, Organization, PipelineItem, SavedSearch, Task, Vendor, ProjectRoom, ProjectRoomPartner, ProjectRoomTask, ProjectRoomNote, ProjectRoomFile, ProjectRoomActivity, OrganizationProfile, NetworkConnection, ProjectRoomInvitation, OrganizationJoinRequest, AwardSyncRun, ConnectorSource, AccountActionToken, OrganizationSecurityPolicy, UserSecurityProfile, ProjectRoomMember, AIConversation, AIMessage, OpportunityDocument, ProposalPlan, PricingPlan, PortfolioSnapshot, AuditLog

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
        self.assertEqual(response.json()["version"], "3.0.4")

    @override_settings(ALLOWED_HOSTS=["forgegov-api.onrender.com"])
    def test_render_health_check_survives_custom_domain_host_transition(self):
        response = APIClient().get("/api/health/", HTTP_HOST="api.example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "3.0.4")


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
        self.assertEqual(len(result["opportunities"]), 1)
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
        self.assertEqual(len(result["results"]), 1)
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

    @override_settings(SBA_SUBNET_URL="https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities", SBA_SUBNET_FALLBACK_URL="")
    @patch("core.integrations.requests.get")
    def test_sba_subnet_parser_separates_title_and_description(self, mock_get):
        response = Mock()
        response.url = "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities"
        response.text = """
            <table><tbody><tr>
              <td><a href='/subnet/opportunity/123'>JLTV Maintenance Support</a> Regional field maintenance subcontract</td>
              <td>08/31/2026</td><td>10/01/2026</td><td>Fort Hood, TX</td><td>811310</td><td>Jane Doe</td>
            </tr></tbody></table>
        """
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = search_sba_subnet_opportunities(query="maintenance", state="TX")

        self.assertIsNone(result["total_records"])
        record = result["results"][0]
        self.assertEqual(record["title"], "JLTV Maintenance Support")
        self.assertEqual(record["description"], "Regional field maintenance subcontract")
        self.assertEqual(record["source_url"], "https://www.sba.gov/subnet/opportunity/123")

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
        self.assertEqual(result["documents"][0]["name"], "pws.pdf")
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
            "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
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


class CommandCenterAndUnifiedSearchTests(AuthenticatedApiTestCase):
    def setUp(self):
        super().setUp()
        self.opportunity = Opportunity.objects.create(source_id="phase5-opp", title="Secure Logistics Support", solicitation_number="FG-2501", agency="Army")
        self.pipeline = PipelineItem.objects.create(organization=self.organization, opportunity=self.opportunity, stage=PipelineItem.Stage.CAPTURE, notes="Priority logistics pursuit")
        Task.objects.create(organization=self.organization, pipeline_item=self.pipeline, title="Submit logistics questions", due_at=timezone.now()-timedelta(days=1))
        self.room = ProjectRoom.objects.create(owner_organization=self.organization, name="Logistics Project Room", status=ProjectRoom.Status.ACTIVE, created_by=self.user)
        ProjectRoomTask.objects.create(project_room=self.room, title="Draft staffing plan", visibility=ProjectRoomTask.Visibility.SHARED, due_date=timezone.localdate()+timedelta(days=2), created_by=self.user)
        ProjectRoomActivity.objects.create(project_room=self.room, actor=self.user, action="task_created", summary="Created staffing task", visibility=ProjectRoomNote.Visibility.SHARED)

    def test_command_center_returns_scoped_operating_picture(self):
        response = self.client.get("/api/dashboard/command-center/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metrics"]["pipeline"], 1)
        self.assertEqual(payload["metrics"]["active_rooms"], 1)
        self.assertGreaterEqual(payload["metrics"]["overdue"], 1)
        self.assertIn("weighted_pipeline", payload["metrics"])
        self.assertIn("intelligence", payload)
        self.assertIn("connectors", payload["intelligence"])
        self.assertIn("stored_awards", payload["intelligence"])
        self.assertTrue(any(row["title"] == "Draft staffing plan" for row in payload["deadlines"]))

    def test_unified_search_finds_workspace_and_intelligence_records(self):
        response = self.client.get("/api/intelligence/search/?q=logistics&limit=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        result_types = {row["type"] for row in payload["results"]}
        self.assertIn("opportunity", result_types)
        self.assertIn("pipeline", result_types)
        self.assertIn("project_room", result_types)
        self.assertIn("Opportunities", payload["groups"])

    def test_partner_command_center_does_not_expose_internal_room_records(self):
        partner_user = User.objects.create_user(username="phase5-partner@example.com", email="phase5-partner@example.com", password="StrongPass!234")
        partner_org = Organization.objects.create(name="Phase Five Partner", slug="phase-five-partner")
        Membership.objects.create(user=partner_user, organization=partner_org, role=Membership.Role.OWNER)
        ProjectRoomPartner.objects.create(project_room=self.room, organization=partner_org, invited_by=self.user)
        ProjectRoomTask.objects.create(project_room=self.room, title="Private pricing action", visibility=ProjectRoomTask.Visibility.INTERNAL, due_date=timezone.localdate()+timedelta(days=1), created_by=self.user)
        ProjectRoomActivity.objects.create(project_room=self.room, actor=self.user, action="private_note", summary="Internal pricing strategy", visibility=ProjectRoomNote.Visibility.INTERNAL)
        client=APIClient(); client.force_authenticate(partner_user)
        payload=client.get("/api/dashboard/command-center/").json()
        self.assertFalse(any(row["title"] == "Private pricing action" for row in payload["deadlines"]))
        self.assertFalse(any(row["title"] == "Internal pricing strategy" for row in payload["activity"]))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="https://forge-gov.test")
class CollaborationStabilityTests(AuthenticatedApiTestCase):
    def test_employee_invitation_sends_email_and_tracks_job_context(self):
        response = self.client.post("/api/team/invitations/", {
            "email": "capture@example.com",
            "role": Membership.Role.CAPTURE,
            "job_title": "Senior Capture Manager",
            "department": "Growth",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["email_delivered"])
        self.assertEqual(len(mail.outbox), 1)
        record = Invitation.objects.get(email="capture@example.com")
        self.assertEqual(record.job_title, "Senior Capture Manager")
        self.assertEqual(record.department, "Growth")
        self.assertIsNotNone(record.last_sent_at)

    def test_invitation_can_be_cancelled_and_history_is_preserved(self):
        invitation = Invitation.objects.create(organization=self.organization, email="viewer@example.com", role=Membership.Role.VIEWER, token="cancel-me", invited_by=self.user, expires_at=timezone.now()+timedelta(days=7))
        response = self.client.post(f"/api/team/invitations/{invitation.id}/action/", {"action": "cancel"}, format="json")
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.CANCELLED)
        self.assertIsNotNone(invitation.responded_at)

    def test_pipeline_returns_canonical_workspace_url(self):
        opportunity = Opportunity.objects.create(source="sam.gov", source_id="notice-261", title="Workspace routing")
        PipelineItem.objects.create(organization=self.organization, opportunity=opportunity)
        response = self.client.get("/api/pipeline/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload["results"]
        self.assertEqual(rows[0]["workspace_url"], "/opportunities/federal-contracts/notice-261")

    def test_suspended_membership_loses_workspace_access(self):
        membership = Membership.objects.get(organization=self.organization, user=self.user)
        membership.active = False
        membership.save(update_fields=["active"])
        response = self.client.get("/api/team/members/")
        self.assertEqual(response.status_code, 403)

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="https://forge-gov.test")
class CollaborationCompletionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="completion-owner@example.com", email="completion-owner@example.com", password="StrongPass!234")
        self.recipient = User.objects.create_user(username="completion-recipient@example.com", email="completion-recipient@example.com", password="StrongPass!234")
        self.organization = Organization.objects.create(name="Completion Prime", slug="completion-prime")
        self.recipient_org = Organization.objects.create(name="Completion Recipient", slug="completion-recipient")
        Membership.objects.create(user=self.owner, organization=self.organization, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.recipient, organization=self.recipient_org, role=Membership.Role.OWNER)
        self.owner_client = APIClient(); self.owner_client.force_authenticate(self.owner)
        self.recipient_client = APIClient(); self.recipient_client.force_authenticate(self.recipient)

    def test_existing_user_sees_email_bound_invitation_and_can_decline(self):
        created = self.owner_client.post("/api/team/invitations/", {"email": self.recipient.email, "role": Membership.Role.VIEWER}, format="json")
        self.assertEqual(created.status_code, 201)
        inbox = self.recipient_client.get("/api/auth/invitations/pending/")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.json()[0]["organization_name"], self.organization.name)
        declined = self.recipient_client.post(f"/api/auth/invitations/{created.json()['id']}/respond/", {"action": "decline"}, format="json")
        self.assertEqual(declined.status_code, 200)
        self.assertEqual(declined.json()["status"], Invitation.Status.DECLINED)

    def test_user_specific_notification_is_visible_across_workspace_boundary(self):
        from .notifications import create_notification
        create_notification(organization=self.organization, user=self.recipient, title="Partner invitation", message="Review request", kind="project_room_invitation", link="/network?tab=invitations")
        response = self.recipient_client.get("/api/collaboration/notifications/")
        self.assertEqual(response.status_code, 200)
        rows = response.json() if isinstance(response.json(), list) else response.json()["results"]
        self.assertTrue(any(row["title"] == "Partner invitation" for row in rows))

    def test_existing_member_can_accept_second_company_membership(self):
        invitation = Invitation.objects.create(organization=self.organization, email=self.recipient.email, role=Membership.Role.VIEWER, token="other-company", expires_at=timezone.now()+timedelta(days=7))
        response = self.recipient_client.post(f"/api/auth/invitations/{invitation.id}/respond/", {"action": "accept"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Membership.objects.filter(user=self.recipient, organization=self.organization, active=True).exists())
        self.assertTrue(Membership.objects.filter(user=self.recipient, organization=self.recipient_org, active=True).exists())

    def test_pipeline_resolver_target_is_independent_of_assigned_team(self):
        opportunity = Opportunity.objects.create(source="sam.gov", source_id="team-independent-notice", title="Team independent route")
        item = PipelineItem.objects.create(organization=self.organization, opportunity=opportunity, assigned_team="Strategic Project Room")
        response = self.owner_client.get(f"/api/pipeline/{item.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workspace_url"], "/opportunities/federal-contracts/team-independent-notice")


class TeamingWorkspaceUsabilityTests(AuthenticatedApiTestCase):
    def test_pipeline_can_create_and_link_teaming_workspace(self):
        opportunity = Opportunity.objects.create(source="sam.gov", source_id="team-room-1", title="Integrated pursuit")
        item = PipelineItem.objects.create(organization=self.organization, opportunity=opportunity)
        response = self.client.post(f"/api/workflow/pipeline/{item.id}/project-room/", {"action":"create","name":"Integrated Pursuit Room"}, format="json")
        self.assertEqual(response.status_code, 201)
        item.refresh_from_db()
        self.assertIsNotNone(item.project_room_id)
        self.assertEqual(response.json()["teaming_workspace_url"], f"/project-rooms/{item.project_room_id}")
        self.assertEqual(response.json()["workspace_url"], "/opportunities/federal-contracts/team-room-1")

    def test_project_room_delete_is_soft_and_unlinks_pipeline(self):
        opportunity = Opportunity.objects.create(source="sam.gov", source_id="team-room-2", title="Delete room pursuit")
        room = ProjectRoom.objects.create(owner_organization=self.organization, opportunity=opportunity, name="Delete Me", created_by=self.user)
        item = PipelineItem.objects.create(organization=self.organization, opportunity=opportunity, project_room=room, assigned_team=room.name)
        response = self.client.post(f"/api/project-rooms/{room.id}/lifecycle/", {"action":"delete"}, format="json")
        self.assertEqual(response.status_code, 200)
        room.refresh_from_db(); item.refresh_from_db()
        self.assertIsNotNone(room.deleted_at)
        self.assertIsNone(item.project_room_id)
        self.assertEqual(item.assigned_team, "")

    def test_domain_join_request_requires_verified_matching_domain(self):
        profile, _ = OrganizationProfile.objects.get_or_create(organization=self.organization)
        profile.website = "https://example.com"; profile.verified = True; profile.save(update_fields=["website", "verified"])
        self.user.email = "owner@example.com"; self.user.save(update_fields=["email"])
        response = self.client.post("/api/company/join-requests/", {"organization":self.organization.id}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(OrganizationJoinRequest.objects.filter(organization=self.organization, user=self.user).exists())

    def test_workspace_switch_cookie_selects_second_membership(self):
        other = Organization.objects.create(name="Second Workspace", slug="second-workspace")
        Membership.objects.create(user=self.user, organization=other, role=Membership.Role.ADMIN)
        response = self.client.post("/api/auth/workspaces/", {"organization":other.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["forgegov_workspace"].value, str(other.id))

class IntelligenceFoundationTests(AuthenticatedApiTestCase):
    def test_connector_manager_returns_normalized_health_rows(self):
        response = self.client.get('/api/intelligence/connectors/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload['summary']['total'], 4)
        self.assertTrue(all({'key','label','configured','status','official_url'} <= set(row) for row in payload['connectors']))

    @patch('core.intelligence.services.opportunity.fetch_sam_opportunity_detail')
    def test_opportunity_intelligence_labels_official_and_derived_data(self, detail):
        detail.return_value = {'title':'JLTV Support','department':'Army','naicsCode':'811310','classificationCode':'J023'}
        Opportunity.objects.create(source_id='intel-1', title='JLTV Support', agency='Army', naics_code='811310', psc_code='J023')
        Award.objects.create(source_id='award-intel-1', recipient_name='Example Incumbent', awarding_agency='Army', naics_code='811310', psc_code='J023', obligated_amount=1000000)
        response = self.client.get('/api/intelligence/opportunities/intel-1/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['data']['incumbent']['name'], 'Example Incumbent')
        self.assertEqual(payload['data']['past_winners'][0]['classification'], 'official')
        self.assertEqual(payload['data']['likely_competitors'][0]['classification'], 'ai_derived')
        self.assertTrue(any(row['source_kind']=='official' for row in payload['evidence']))


class AwardIngestionAndConnectorSdkTests(AuthenticatedApiTestCase):
    def test_connector_registry_includes_federal_and_state_reference(self):
        response = self.client.get("/api/intelligence/connector-registry/")
        self.assertEqual(response.status_code, 200)
        keys = {row["key"] for row in response.json()["connectors"]}
        self.assertIn("usaspending-awards", keys)
        self.assertIn("texas-smartbuy-reference", keys)
        texas = next(row for row in response.json()["connectors"] if row["key"] == "texas-smartbuy-reference")
        self.assertEqual(texas["scope"], "state")
        self.assertEqual(texas["jurisdiction_code"], "TX")
        self.assertIn("license_name", texas)

    def test_award_summary_uses_official_stored_awards(self):
        Award.objects.create(
            source="usaspending.gov",
            source_id="CONT_AWD_TEST_1",
            award_number="WTEST-001",
            recipient_name="HOWARD DYNAMICS LLC",
            awarding_agency="Department of the Army",
            obligated_amount=125000,
            potential_amount=200000,
            naics_code="811310",
            jurisdiction_level="federal",
            jurisdiction_code="US",
        )
        response = self.client.get("/api/intelligence/awards/summary/?agency=Army&naics=811310")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["totals"]["records"], 1)
        self.assertEqual(payload["likely_incumbent"]["recipient_name"], "HOWARD DYNAMICS LLC")
        self.assertEqual(payload["classification"], "official_historical_awards")

    @patch("core.views.sync_usaspending_awards")
    def test_owner_can_start_award_ingestion(self, mocked_sync):
        mocked_sync.return_value = type("Run", (), {
            "id": 99,
            "status": "succeeded",
            "records_seen": 5,
            "records_created": 3,
            "records_updated": 2,
            "errors": [],
        })()
        response = self.client.post("/api/intelligence/awards/ingestion/", {"pages": 1, "limit": 5}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["records_created"], 3)


class DocumentIntelligenceStructuredExtractionTests(SimpleTestCase):
    def test_structured_intelligence_extracts_core_solicitation_signals(self):
        from .document_intelligence import extract_structured_intelligence

        sections = [
            (
                1,
                None,
                """
                SECTION L - INSTRUCTIONS TO OFFERORS
                CLIN 0001
                Deliverable: Monthly status report
                FAR 52.212-1
                DFARS 252.204-7012
                CMMC Level 2
                Questions due August 20, 2026
                """,
            ),
            (
                2,
                None,
                """
                SECTION M - EVALUATION FACTORS FOR AWARD
                Labor Categories: Field Service Representative
                """,
            ),
        ]

        result = extract_structured_intelligence(sections)

        self.assertTrue(result["section_l_detected"])
        self.assertTrue(result["section_m_detected"])
        self.assertIn("0001", result["clins"])
        self.assertTrue(any("252.204-7012" in clause for clause in result["clauses"]))
        self.assertTrue(any("CMMC" in certification for certification in result["certifications"]))
        self.assertTrue(result["deliverables"])
        self.assertTrue(result["labor_categories"])

    def test_zip_ingestion_reads_supported_members(self):
        import io
        import zipfile
        from .document_intelligence import extract_document

        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("scope.txt", "SECTION L\\nCLIN 0002\\nDeliverable: Final report")
            archive.writestr("ignored.exe", "not indexed")

        sections = extract_document(payload.getvalue(), "attachments.zip", "application/zip")

        self.assertEqual(len(sections), 1)
        self.assertIn("scope.txt", sections[0][1])
        self.assertIn("CLIN 0002", sections[0][2])


class CaptureAssessmentTests(AuthenticatedApiTestCase):
    def test_capture_assessment_returns_decision_scores_without_ai(self):
        opportunity = Opportunity.objects.create(
            source_id="capture-1",
            title="Vehicle maintenance support",
            agency="Department of the Army",
            naics_code="811310",
            psc_code="J023",
            response_deadline=timezone.now() + timedelta(days=21),
        )
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.REVIEWING,
            estimated_value=500000,
            probability_of_win=55,
        )
        payload = build_capture_assessment(
            organization=self.organization,
            opportunity=opportunity,
            include_ai=False,
            user=self.user,
        )
        self.assertIn(payload["bid_decision"]["recommendation"], {"bid", "hold", "no_bid"})
        self.assertGreaterEqual(payload["scores"]["health"], 0)
        self.assertLessEqual(payload["scores"]["health"], 100)
        self.assertEqual(len(payload["risks"]), 6)
        self.assertTrue(payload["actions"])

    def test_capture_assessment_endpoint_is_workspace_scoped(self):
        Opportunity.objects.create(
            source_id="capture-api-1",
            title="Logistics support",
            response_deadline=timezone.now() + timedelta(days=30),
        )
        response = self.client.get("/api/ai/opportunities/capture-api-1/capture-assessment/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("scores", body)
        self.assertIn("bid_decision", body)
        self.assertIn("readiness", body)


class WinStrategyTests(AuthenticatedApiTestCase):
    def test_win_strategy_returns_evidence_backed_sections(self):
        opportunity = Opportunity.objects.create(
            source_id="win-1",
            title="Vehicle maintenance support",
            agency="Department of the Army",
            naics_code="811310",
            psc_code="J023",
            response_deadline=timezone.now() + timedelta(days=30),
        )
        Award.objects.create(
            source_id="award-win-1",
            award_number="W56TEST001",
            recipient_name="EXAMPLE MAINTENANCE LLC",
            awarding_agency="Department of the Army",
            obligated_amount=2500000,
            start_date=timezone.now().date() - timedelta(days=365),
            end_date=timezone.now().date() + timedelta(days=180),
            naics_code="811310",
            psc_code="J023",
            description="Vehicle maintenance and repair support",
        )
        payload = build_win_strategy(organization=self.organization, opportunity=opportunity)
        self.assertEqual(payload["incumbent"]["status"], "likely")
        self.assertTrue(payload["similar_contracts"])
        self.assertIn("pricing_readiness", payload)
        self.assertIn("win_strategy", payload)
        self.assertIn("compliance_matrix", payload)

    def test_win_strategy_endpoint_is_workspace_scoped(self):
        Opportunity.objects.create(source_id="win-api-1", title="Logistics support", agency="Army")
        response = self.client.get("/api/ai/opportunities/win-api-1/win-strategy/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("incumbent", body)
        self.assertIn("competitors", body)
        self.assertIn("teaming_recommendations", body)
        self.assertIn("recommended_actions", body)

class CaptureCommandCenterTests(AuthenticatedApiTestCase):
    def test_command_center_combines_capture_and_win_strategy(self):
        opportunity = Opportunity.objects.create(
            source_id="command-center-1",
            title="Fleet maintenance support",
            agency="Department of the Army",
            naics_code="811310",
            psc_code="J023",
            response_deadline=timezone.now() + timedelta(days=21),
        )
        pipeline = PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=5000000,
            probability_of_win=65,
            notes="Customer values rapid field support and parts availability.",
        )
        Task.objects.create(
            organization=self.organization,
            pipeline_item=pipeline,
            title="Validate staffing plan",
            due_at=timezone.now() + timedelta(days=3),
        )
        Award.objects.create(
            source_id="command-award-1",
            award_number="W56COMMAND001",
            recipient_name="EXAMPLE SERVICES LLC",
            awarding_agency="Department of the Army",
            obligated_amount=3000000,
            start_date=timezone.now().date() - timedelta(days=365),
            end_date=timezone.now().date() + timedelta(days=120),
            naics_code="811310",
            psc_code="J023",
            description="Fleet vehicle maintenance and field support",
        )
        from .capture_command_center import build_capture_command_center
        payload = build_capture_command_center(organization=self.organization, opportunity=opportunity)
        self.assertIn("scores", payload)
        self.assertIn("next_actions", payload)
        self.assertIn("capture_memory", payload)
        self.assertIn("proposal_tasks", payload)
        self.assertIn("competition", payload)
        self.assertEqual(payload["proposal_tasks"][0]["title"], "Validate staffing plan")
        self.assertTrue(any(row["type"] == "pipeline" for row in payload["capture_memory"]))

    def test_command_center_endpoint_is_workspace_scoped(self):
        Opportunity.objects.create(source_id="command-api-1", title="Command center test", agency="Army")
        response = self.client.get("/api/ai/opportunities/command-api-1/command-center/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("health", body)
        self.assertIn("timeline", body)
        self.assertIn("warnings", body)


class ProposalWorkspaceRouteTests(TestCase):
    def test_proposal_workspace_route_is_registered(self):
        from django.urls import resolve
        match = resolve('/api/ai/opportunities/example/proposal-workspace/')
        self.assertEqual(match.func.__name__, 'view')


class ProposalExecutionTests(AuthenticatedApiTestCase):
    def test_proposal_execution_seeds_persistent_requirements_and_reviews(self):
        opportunity = Opportunity.objects.create(
            source_id="proposal-execution-1",
            title="Maintenance proposal",
            agency="Department of the Army",
            response_deadline=timezone.now() + timedelta(days=30),
        )
        OpportunityWorkspace.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            compliance_items=[
                {"id": "workspace-req", "label": "Submit technical volume", "complete": False, "source": "Section L"},
            ],
        )
        response = self.client.get("/api/ai/opportunities/proposal-execution-1/proposal-execution/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["counts"]["requirements_total"], 1)
        self.assertEqual(body["counts"]["reviews_total"], 4)
        self.assertIn("amendment_impact", body)
        self.assertIn("members", body)
        from .models import ProposalPlan, ProposalRequirement, ProposalReview
        plan = ProposalPlan.objects.get(organization=self.organization, opportunity=opportunity)
        self.assertTrue(ProposalRequirement.objects.filter(plan=plan, key="workspace-req").exists())
        self.assertEqual(ProposalReview.objects.filter(plan=plan).count(), 4)

    def test_requirement_update_is_workspace_scoped_and_persistent(self):
        opportunity = Opportunity.objects.create(
            source_id="proposal-execution-2",
            title="Logistics proposal",
            response_deadline=timezone.now() + timedelta(days=25),
        )
        first = self.client.get("/api/ai/opportunities/proposal-execution-2/proposal-execution/")
        requirement_id = first.json()["requirements"][0]["id"]
        response = self.client.patch(
            f"/api/ai/opportunities/proposal-execution-2/proposal-requirements/{requirement_id}/",
            {"status": "in_progress", "owner_id": self.user.id, "notes": "Assigned for response drafting."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.json()["requirements"] if item["id"] == requirement_id)
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(row["owner_id"], self.user.id)

    def test_submission_ready_requires_human_gates(self):
        opportunity = Opportunity.objects.create(
            source_id="proposal-execution-3",
            title="Field support proposal",
            response_deadline=timezone.now() + timedelta(days=35),
        )
        response = self.client.get("/api/ai/opportunities/proposal-execution-3/proposal-execution/")
        body = response.json()
        self.assertFalse(body["plan"]["submission_ready"])
        self.assertFalse(body["plan"]["final_submission_verified"])

    def test_proposal_execution_route_is_registered(self):
        from django.urls import resolve
        match = resolve("/api/ai/opportunities/example/proposal-execution/")
        self.assertEqual(match.func.__name__, "view")


class SubmissionControlTests(AuthenticatedApiTestCase):
    def test_submission_control_route_is_registered(self):
        from django.urls import resolve
        match = resolve("/api/ai/opportunities/example/submission-control/")
        self.assertEqual(match.func.__name__, "view")
        export_match = resolve("/api/ai/opportunities/example/submission-exports/pdf/")
        self.assertEqual(export_match.func.__name__, "view")

    def test_submission_control_blocks_snapshot_until_human_gates_are_clear(self):
        opportunity = Opportunity.objects.create(
            source_id="submission-control-1",
            title="Submission control proposal",
            agency="Department of the Army",
            response_deadline=timezone.now() + timedelta(days=20),
        )
        response = self.client.get("/api/ai/opportunities/submission-control-1/submission-control/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["submission_readiness"]["ready"])
        self.assertGreater(len(body["submission_readiness"]["blockers"]), 0)
        submit = self.client.post(
            "/api/ai/opportunities/submission-control-1/submission-control/",
            {"action": "submit", "confirmation_reference": "TEST-RECEIPT"},
            format="json",
        )
        self.assertEqual(submit.status_code, 400)

    def test_closeout_is_company_workspace_scoped(self):
        opportunity = Opportunity.objects.create(
            source_id="submission-control-2",
            title="Closeout proposal",
            response_deadline=timezone.now() + timedelta(days=10),
        )
        self.client.get("/api/ai/opportunities/submission-control-2/submission-control/")
        response = self.client.post(
            "/api/ai/opportunities/submission-control-2/submission-control/",
            {"action": "update_closeout", "status": "evaluation", "debrief_requested": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["closeout"]["status"], "evaluation")
        self.assertTrue(response.json()["closeout"]["debrief_requested"])


class PursuitDecisionIntelligenceTests(AuthenticatedApiTestCase):
    def test_pursuit_decision_is_explainable_and_persistent(self):
        opportunity = Opportunity.objects.create(
            source_id="decision-m4-1", title="Vehicle sustainment", agency="Department of the Army",
            naics_code="811310", psc_code="J023", response_deadline=timezone.now() + timedelta(days=30),
        )
        PipelineItem.objects.create(
            organization=self.organization, opportunity=opportunity, stage=PipelineItem.Stage.CAPTURE,
            estimated_value=1000000, probability_of_win=50,
        )
        response = self.client.get("/api/ai/opportunities/decision-m4-1/pursuit-decision/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["decision"]["recommendation"], ["PURSUE", "PURSUE WITH CONDITIONS", "HOLD", "NO-BID"])
        self.assertEqual(sum(row["weight"] for row in body["scorecard"]), 100)
        self.assertIn("evidence", body)
        created = self.client.post("/api/ai/opportunities/decision-m4-1/pursuit-decision/", {}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json().get("recorded_snapshot_id"))

    def test_command_center_includes_pursuit_decision_without_new_tab(self):
        Opportunity.objects.create(source_id="decision-m4-2", title="Decision command center", agency="Army")
        response = self.client.get("/api/ai/opportunities/decision-m4-2/command-center/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("pursuit_decision", response.json())


class AiResponseDocumentHardeningTests(AuthenticatedApiTestCase):
    def test_public_html_description_is_cleaned_to_readable_text(self):
        from .integrations import _clean_public_text
        raw = "<p><strong>Road Reconstruction</strong></p><p>Response Period: August 9 through August 14</p>"
        cleaned = _clean_public_text(raw)
        self.assertIn("Road Reconstruction", cleaned)
        self.assertIn("Response Period", cleaned)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("<strong>", cleaned)

    def test_ai_chat_accepts_more_than_old_8000_character_limit(self):
        with patch("core.views.ask_ai") as mocked:
            mocked.return_value = {
                "answer": "Structured answer",
                "model": "test-model",
                "provider": "openai",
                "sources": [],
            }
            response = self.client.post(
                "/api/ai/chat/",
                {"message": "A" * 12000, "history": []},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Structured answer")

    def test_opportunity_context_cleans_description_and_surfaces_poc(self):
        from .views import _opportunity_context
        opportunity = Opportunity.objects.create(
            source_id="m5-context-1",
            title="Road project",
            description="<p>Reconstruct the access road.</p>",
            agency="USDA Forest Service",
            office="Santa Fe National Forest",
            place_of_performance="New Mexico",
            raw_data={
                "pointOfContact": [
                    {"fullName": "Jane Doe", "email": "jane@example.gov", "phone": "555-0100"}
                ]
            },
        )
        context, _ = _opportunity_context(opportunity)
        self.assertIn("Description: Reconstruct the access road.", context)
        self.assertIn("POC: Jane Doe", context)
        self.assertIn("jane@example.gov", context)
        self.assertNotIn("<p>", context)

    def test_document_context_covers_multiple_indexed_documents(self):
        from .models import OpportunityDocument, OpportunityDocumentChunk
        from .views import _document_context
        opportunity = Opportunity.objects.create(source_id="m5-doc-coverage", title="Coverage test")
        first = OpportunityDocument.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            file_name="Section L.pdf",
            source_url="https://example.gov/l.pdf",
            status=OpportunityDocument.Status.READY,
        )
        second = OpportunityDocument.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            file_name="Section M.pdf",
            source_url="https://example.gov/m.pdf",
            status=OpportunityDocument.Status.READY,
        )
        OpportunityDocumentChunk.objects.create(document=first, ordinal=0, text="Submission instructions and volume requirements.")
        OpportunityDocumentChunk.objects.create(document=second, ordinal=0, text="Evaluation factors and technical approach.")
        context, sources = _document_context(self.organization, opportunity, query="evaluation submission")
        self.assertIn("Section L.pdf", context)
        self.assertIn("Section M.pdf", context)
        self.assertGreaterEqual(len(sources), 2)


class PricingEngineTests(AuthenticatedApiTestCase):
    def test_pricing_workspace_creates_plan_and_default_scenarios(self):
        opportunity = Opportunity.objects.create(
            source_id="pricing-m1-1",
            title="Pricing foundation test",
            agency="Department of the Navy",
        )
        response = self.client.get("/api/pricing/opportunities/pricing-m1-1/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["plan"]["revision"], 1)
        self.assertEqual(body["plan"]["status"], "draft")
        self.assertEqual(len(body["scenarios"]), 3)
        self.assertEqual(float(body["totals"]["price"]), 0.0)

    def test_pricing_engine_calculates_labor_burden_and_profit(self):
        opportunity = Opportunity.objects.create(source_id="pricing-m1-2", title="Labor pricing")
        self.client.patch(
            "/api/pricing/opportunities/pricing-m1-2/",
            {
                "action": "update_plan",
                "payroll_burden_percent": "10",
                "fringe_percent": "20",
                "overhead_percent": "10",
                "ga_percent": "10",
                "target_profit_percent": "10",
            },
            format="json",
        )
        response = self.client.patch(
            "/api/pricing/opportunities/pricing-m1-2/",
            {
                "action": "add_item",
                "category": "labor",
                "name": "Senior Technician",
                "labor_hours": "100",
                "labor_rate": "50",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        totals = response.json()["totals"]
        self.assertEqual(float(totals["direct"]), 5000.0)
        self.assertGreater(float(totals["total_cost"]), 5000.0)
        self.assertGreater(float(totals["price"]), float(totals["total_cost"]))
        self.assertGreater(float(totals["profit"]), 0.0)

    def test_pricing_revision_preserves_financial_history(self):
        opportunity = Opportunity.objects.create(source_id="pricing-m1-3", title="Revision test")
        self.client.patch(
            "/api/pricing/opportunities/pricing-m1-3/",
            {"action": "add_item", "category": "material", "name": "Parts", "quantity": "2", "unit_cost": "1000"},
            format="json",
        )
        response = self.client.patch(
            "/api/pricing/opportunities/pricing-m1-3/",
            {"action": "new_revision"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plan"]["revision"], 2)
        self.assertEqual(len(response.json()["items"]), 1)
        from .models import PricingPlan
        revisions = list(PricingPlan.objects.filter(organization=self.organization, opportunity=opportunity).order_by("revision"))
        self.assertEqual(len(revisions), 2)
        self.assertEqual(revisions[0].status, "locked")

    def test_pursuit_decision_consumes_real_pricing_economics(self):
        opportunity = Opportunity.objects.create(source_id="pricing-m1-4", title="Decision economics", agency="Army")
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=900000,
            probability_of_win=50,
        )
        self.client.patch(
            "/api/pricing/opportunities/pricing-m1-4/",
            {"action": "add_item", "category": "subcontract", "name": "Prime subcontract", "quantity": "1", "unit_cost": "500000"},
            format="json",
        )
        pricing = self.client.get("/api/pricing/opportunities/pricing-m1-4/").json()
        decision = self.client.get("/api/ai/opportunities/pricing-m1-4/pursuit-decision/")
        self.assertEqual(decision.status_code, 200)
        economics = decision.json()["economics"]
        self.assertEqual(float(economics["estimated_value"]), float(pricing["totals"]["price"]))
        self.assertEqual(float(economics["target_margin_percent"]), float(pricing["totals"]["margin_percent"]))
        self.assertEqual(economics["pricing_revision"], 1)


class PriceToWinIntelligenceTests(AuthenticatedApiTestCase):
    def _seed_awards(self):
        from datetime import date
        from .models import Award
        values = [800000, 900000, 1000000, 1100000, 1200000]
        for index, value in enumerate(values, 1):
            Award.objects.create(
                source="usaspending.gov",
                source_id=f"ptw-award-{index}",
                award_number=f"W91PTW{index}",
                award_type=Award.AwardType.CONTRACT,
                recipient_name=f"Comparable Contractor {index}",
                awarding_agency="Department of the Army",
                obligated_amount=value,
                potential_amount=value,
                naics_code="541330",
                psc_code="R425",
                start_date=date(2025, index, 1),
                source_url=f"https://example.gov/awards/{index}",
            )

    def test_price_to_win_builds_evidence_backed_range(self):
        opportunity = Opportunity.objects.create(
            source_id="ptw-m2-1",
            title="Engineering support",
            agency="Department of the Army",
            naics_code="541330",
            psc_code="R425",
        )
        self._seed_awards()
        response = self.client.get("/api/pricing/opportunities/ptw-m2-1/price-to-win/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification"], "derived_from_official_historical_awards")
        self.assertGreaterEqual(body["evidence_count"], 5)
        self.assertGreater(body["confidence"], 0)
        self.assertIsNotNone(body["range"]["competitive_floor"])
        self.assertIsNotNone(body["range"]["target"])
        self.assertIsNotNone(body["range"]["protective_ceiling"])
        self.assertLessEqual(float(body["range"]["competitive_floor"]), float(body["range"]["target"]))
        self.assertLessEqual(float(body["range"]["target"]), float(body["range"]["protective_ceiling"]))

    def test_price_to_win_compares_market_range_to_real_cost_model(self):
        opportunity = Opportunity.objects.create(
            source_id="ptw-m2-2",
            title="Engineering support economics",
            agency="Department of the Army",
            naics_code="541330",
            psc_code="R425",
        )
        self._seed_awards()
        self.client.patch(
            "/api/pricing/opportunities/ptw-m2-2/",
            {"action": "add_item", "category": "subcontract", "name": "Delivery subcontract", "quantity": "1", "unit_cost": "750000"},
            format="json",
        )
        response = self.client.get("/api/pricing/opportunities/ptw-m2-2/price-to-win/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNotNone(body["current_pricing"]["price"])
        self.assertIsNotNone(body["viability"]["modeled_target"]["margin_percent"])
        self.assertIn(
            body["current_pricing"]["position"],
            ["below_competitive_floor", "competitive", "above_target_within_range", "above_modeled_range"],
        )

    def test_price_to_win_snapshot_is_persistent(self):
        from .models import PriceToWinSnapshot
        opportunity = Opportunity.objects.create(
            source_id="ptw-m2-3",
            title="Snapshot test",
            agency="Department of the Army",
            naics_code="541330",
            psc_code="R425",
        )
        self._seed_awards()
        response = self.client.post("/api/pricing/opportunities/ptw-m2-3/price-to-win/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get("recorded_snapshot_id"))
        self.assertEqual(
            PriceToWinSnapshot.objects.filter(organization=self.organization, opportunity=opportunity).count(),
            1,
        )

    def test_pursuit_decision_surfaces_price_to_win_economics(self):
        opportunity = Opportunity.objects.create(
            source_id="ptw-m2-4",
            title="Decision PTW integration",
            agency="Department of the Army",
            naics_code="541330",
            psc_code="R425",
        )
        self._seed_awards()
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=1000000,
            probability_of_win=50,
        )
        self.client.patch(
            "/api/pricing/opportunities/ptw-m2-4/",
            {"action": "add_item", "category": "material", "name": "Delivery inputs", "quantity": "1", "unit_cost": "700000"},
            format="json",
        )
        response = self.client.get("/api/ai/opportunities/ptw-m2-4/pursuit-decision/")
        self.assertEqual(response.status_code, 200)
        economics = response.json()["economics"]
        self.assertIsNotNone(economics["price_to_win_target"])
        self.assertGreater(economics["price_to_win_confidence"], 0)
        self.assertIn("price_position", economics)


class PrimeSubCashFlowTests(AuthenticatedApiTestCase):
    def test_subcontractor_economics_calculate_prime_contribution(self):
        opportunity = Opportunity.objects.create(source_id="m3-sub-1", title="Prime sub economics")
        response = self.client.patch(
            "/api/pricing/opportunities/m3-sub-1/prime-sub-cashflow/",
            {
                "action": "add_subcontractor",
                "name": "ABC Construction",
                "quoted_cost": "100000",
                "prime_markup_percent": "12",
                "management_burden": "3000",
                "insurance_cost": "1000",
                "contingency": "2000",
                "deposit_percent": "10",
                "payment_terms_days": 15,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["subcontractors"]), 1)
        row = body["subcontractors"][0]
        self.assertEqual(float(row["prime_revenue"]), 112000.0)
        self.assertEqual(float(row["net_contribution"]), 6000.0)
        self.assertEqual(float(row["deposit_required"]), 10000.0)
        self.assertGreater(float(row["effective_margin_percent"]), 5.0)

    def test_cashflow_model_flags_working_capital_gap(self):
        opportunity = Opportunity.objects.create(source_id="m3-cash-1", title="Cash flow economics")
        self.client.patch(
            "/api/pricing/opportunities/m3-cash-1/",
            {
                "action": "add_item",
                "category": "labor",
                "name": "Delivery team",
                "labor_hours": "12000",
                "labor_rate": "50",
            },
            format="json",
        )
        response = self.client.patch(
            "/api/pricing/opportunities/m3-cash-1/prime-sub-cashflow/",
            {
                "action": "update_cashflow",
                "performance_months": "12",
                "payment_lag_days": 60,
                "mobilization_cost": "50000",
                "available_working_capital": "10000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        cashflow = response.json()["cashflow"]
        self.assertGreater(float(cashflow["recommended_working_capital"]), 10000.0)
        self.assertGreater(float(cashflow["working_capital_gap"]), 0.0)
        self.assertIn(cashflow["risk"], ["high", "critical"])
        self.assertTrue(cashflow["warnings"])

    def test_pricing_revision_preserves_subcontractor_and_cashflow_assumptions(self):
        from .models import PricingPlan
        opportunity = Opportunity.objects.create(source_id="m3-rev-1", title="M3 revision")
        self.client.patch(
            "/api/pricing/opportunities/m3-rev-1/prime-sub-cashflow/",
            {
                "action": "add_subcontractor",
                "name": "Specialty Vendor",
                "quoted_cost": "250000",
                "prime_markup_percent": "10",
            },
            format="json",
        )
        self.client.patch(
            "/api/pricing/opportunities/m3-rev-1/prime-sub-cashflow/",
            {
                "action": "update_cashflow",
                "performance_months": "18",
                "payment_lag_days": 45,
                "available_working_capital": "300000",
            },
            format="json",
        )
        response = self.client.patch(
            "/api/pricing/opportunities/m3-rev-1/",
            {"action": "new_revision"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plan"]["revision"], 2)
        newest = PricingPlan.objects.filter(organization=self.organization, opportunity=opportunity).order_by("-revision").first()
        self.assertEqual(newest.payment_lag_days, 45)
        self.assertEqual(float(newest.performance_months), 18.0)
        self.assertEqual(newest.subcontractors.count(), 1)

    def test_pursuit_decision_surfaces_liquidity_risk(self):
        opportunity = Opportunity.objects.create(source_id="m3-decision-1", title="M3 decision economics")
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=900000,
            probability_of_win=50,
        )
        self.client.patch(
            "/api/pricing/opportunities/m3-decision-1/",
            {
                "action": "add_item",
                "category": "labor",
                "name": "Labor",
                "labor_hours": "10000",
                "labor_rate": "50",
            },
            format="json",
        )
        self.client.patch(
            "/api/pricing/opportunities/m3-decision-1/prime-sub-cashflow/",
            {
                "action": "update_cashflow",
                "performance_months": "12",
                "payment_lag_days": 60,
                "available_working_capital": "0",
            },
            format="json",
        )
        response = self.client.get("/api/ai/opportunities/m3-decision-1/pursuit-decision/")
        self.assertEqual(response.status_code, 200)
        economics = response.json()["economics"]
        self.assertIn(economics["working_capital_risk"], ["high", "critical"])
        self.assertGreater(float(economics["recommended_working_capital"]), 0.0)
        self.assertGreaterEqual(float(economics["working_capital_gap"]), 0.0)


class PortfolioIntelligenceTests(AuthenticatedApiTestCase):
    def test_portfolio_rolls_up_pipeline_pricing_profit_and_working_capital(self):
        opportunity = Opportunity.objects.create(
            source_id="m4-portfolio-1",
            title="Portfolio economics test",
            agency="Department of the Navy",
        )
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.PROPOSAL,
            estimated_value=1000000,
            probability_of_win=60,
        )
        self.client.patch(
            "/api/pricing/opportunities/m4-portfolio-1/",
            {
                "action": "add_item",
                "category": "labor",
                "name": "Delivery labor",
                "labor_hours": "10000",
                "labor_rate": "50",
            },
            format="json",
        )
        self.client.patch(
            "/api/pricing/opportunities/m4-portfolio-1/prime-sub-cashflow/",
            {
                "action": "update_cashflow",
                "performance_months": "12",
                "payment_lag_days": 45,
                "available_working_capital": "10000",
            },
            format="json",
        )

        response = self.client.get("/api/reports/portfolio-intelligence/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["active_opportunity_count"], 1)
        self.assertEqual(body["summary"]["priced_opportunity_count"], 1)
        self.assertGreater(float(body["summary"]["pipeline_value"]), 0.0)
        self.assertGreater(float(body["summary"]["weighted_pipeline_value"]), 0.0)
        self.assertGreater(float(body["summary"]["projected_profit"]), 0.0)
        self.assertGreater(float(body["summary"]["recommended_working_capital"]), 0.0)
        self.assertEqual(body["agency_concentration"][0]["agency"], "Department of the Navy")

    def test_portfolio_excludes_lost_and_no_bid_pipeline(self):
        active = Opportunity.objects.create(source_id="m4-active", title="Active", agency="Army")
        lost = Opportunity.objects.create(source_id="m4-lost", title="Lost", agency="Army")
        no_bid = Opportunity.objects.create(source_id="m4-nobid", title="No Bid", agency="Army")
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=active,
            stage=PipelineItem.Stage.CAPTURE,
            estimated_value=500000,
            probability_of_win=50,
        )
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=lost,
            stage=PipelineItem.Stage.LOST,
            estimated_value=900000,
            probability_of_win=0,
        )
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=no_bid,
            stage=PipelineItem.Stage.NO_BID,
            estimated_value=700000,
            probability_of_win=0,
        )

        response = self.client.get("/api/reports/portfolio-intelligence/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["active_opportunity_count"], 1)
        self.assertEqual(float(body["summary"]["pipeline_value"]), 500000.0)

    def test_portfolio_snapshot_persists_executive_history(self):
        from .models import PortfolioSnapshot

        opportunity = Opportunity.objects.create(source_id="m4-snapshot", title="Snapshot", agency="Air Force")
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.QUALIFIED,
            estimated_value=250000,
            probability_of_win=25,
        )
        response = self.client.post("/api/reports/portfolio-intelligence/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get("recorded_snapshot_id"))
        self.assertEqual(PortfolioSnapshot.objects.filter(organization=self.organization).count(), 1)

        history = self.client.get("/api/reports/portfolio-intelligence/").json()["history"]
        self.assertEqual(len(history), 1)

    def test_portfolio_customer_concentration_creates_risk_signal(self):
        for index, value in enumerate([800000, 100000], 1):
            opportunity = Opportunity.objects.create(
                source_id=f"m4-concentration-{index}",
                title=f"Concentration {index}",
                agency="Department of the Army" if index == 1 else "Department of Energy",
            )
            PipelineItem.objects.create(
                organization=self.organization,
                opportunity=opportunity,
                stage=PipelineItem.Stage.CAPTURE,
                estimated_value=value,
                probability_of_win=50,
            )

        response = self.client.get("/api/reports/portfolio-intelligence/")
        self.assertEqual(response.status_code, 200)
        risks = response.json()["risks"]
        self.assertTrue(any(row["title"] == "Customer concentration" for row in risks))

class WorkspaceConsolidationTests(AuthenticatedApiTestCase):
    def test_command_summary_returns_cross_module_state_without_requiring_pricing(self):
        opportunity = Opportunity.objects.create(
            source_id="v301-command-summary",
            title="Workspace consolidation test",
            agency="Department of the Army",
        )
        PipelineItem.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            stage=PipelineItem.Stage.CAPTURE,
            probability_of_win=55,
            next_action="Validate customer hot buttons",
        )
        response = self.client.get("/api/workflow/opportunities/v301-command-summary/command-summary/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["pipeline"]["active"])
        self.assertEqual(body["pipeline"]["stage"], PipelineItem.Stage.CAPTURE)
        self.assertEqual(body["pricing"]["status"], "not_started")
        self.assertIn(body["proposal"]["status"], {"not_started", "planning"})
        self.assertIn("decision", body)
        self.assertIn("documents", body)

    def test_command_summary_reflects_workspace_compliance_progress(self):
        opportunity = Opportunity.objects.create(
            source_id="v301-compliance-summary",
            title="Compliance command summary",
            agency="Department of the Navy",
        )
        OpportunityWorkspace.objects.create(
            organization=self.organization,
            opportunity=opportunity,
            compliance_items=[
                {"id": "one", "label": "First", "complete": True},
                {"id": "two", "label": "Second", "complete": False},
            ],
        )
        response = self.client.get("/api/workflow/opportunities/v301-compliance-summary/command-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["compliance"], {"complete": 1, "total": 2, "percent": 50})


@override_settings(
    REGISTRATION_MODE="public",
    BUSINESS_EMAIL_REQUIRED=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
    AXES_ENABLED=False,
)
class IdentityFoundationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_registration_requires_terms_and_privacy_acceptance(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.test",
                "password": "LongSecurePassphrase123",
                "organization_name": "Acme Federal",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Terms", response.json()["detail"])

    def test_public_registration_requires_email_verification_before_login(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.test",
                "password": "LongSecurePassphrase123",
                "organization_name": "Acme Federal",
                "accept_terms": True,
                "accept_privacy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["email_verified"])
        user = User.objects.get(email="jane@acme.test")
        self.assertFalse(user.is_active)
        self.assertIsNone(user.forgegov_security.email_verified_at)
        self.assertEqual(len(mail.outbox), 1)

        blocked = self.client.post(
            "/api/auth/login/",
            {"email": "jane@acme.test", "password": "LongSecurePassphrase123"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "email_unverified")

    def test_email_verification_activates_identity(self):
        self.client.post(
            "/api/auth/register/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.test",
                "password": "LongSecurePassphrase123",
                "organization_name": "Acme Federal",
                "accept_terms": True,
                "accept_privacy": True,
            },
            format="json",
        )
        body = mail.outbox[0].body
        token = body.split("token=", 1)[1].strip()
        verified = self.client.post("/api/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["verified"])
        user = User.objects.get(email="jane@acme.test")
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.forgegov_security.email_verified_at)
        self.assertEqual(user.forgegov_security.lifecycle_status, UserSecurityProfile.LifecycleStatus.ACTIVE)

    def test_same_business_domain_routes_to_join_request_instead_of_duplicate_org(self):
        existing = Organization.objects.create(name="Acme Federal", slug="acme-federal", business_domain="acme.test")
        owner = User.objects.create_user(username="owner@acme.test", email="owner@acme.test", password="LongSecurePassphrase123")
        Membership.objects.create(organization=existing, user=owner, role=Membership.Role.OWNER)

        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.test",
                "password": "AnotherSecurePassphrase123",
                "organization_name": "Duplicate Acme",
                "accept_terms": True,
                "accept_privacy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Organization.objects.filter(business_domain="acme.test").count(), 1)
        user = User.objects.get(email="jane@acme.test")
        self.assertEqual(user.forgegov_security.pending_organization_id, existing.id)
        self.assertFalse(OrganizationJoinRequest.objects.filter(organization=existing, user=user, status="pending").exists())
        self.assertFalse(Membership.objects.filter(organization=existing, user=user).exists())

        token = mail.outbox[0].body.split("token=", 1)[1].strip()
        verified = self.client.post("/api/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["next_step"], "pending_organization_approval")
        self.assertTrue(OrganizationJoinRequest.objects.filter(organization=existing, user=user, status="pending").exists())

    @override_settings(REGISTRATION_MODE="private_beta")
    def test_private_beta_requires_company_invitation(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.test",
                "password": "LongSecurePassphrase123",
                "organization_name": "Acme Federal",
                "accept_terms": True,
                "accept_privacy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["registration_mode"], "private_beta")

    @override_settings(REGISTRATION_MODE="private_beta")
    def test_invitation_registration_is_email_verified_and_enters_workspace(self):
        organization = Organization.objects.create(name="Prime Co", slug="prime-co", business_domain="prime.test")
        owner = User.objects.create_user(username="owner@prime.test", email="owner@prime.test", password="LongSecurePassphrase123")
        Membership.objects.create(organization=organization, user=owner, role=Membership.Role.OWNER)
        invitation = Invitation.objects.create(
            organization=organization,
            email="new@prime.test",
            role=Membership.Role.CAPTURE,
            token="secure-invite-token",
            expires_at=timezone.now() + timedelta(days=7),
        )
        response = self.client.post(
            "/api/auth/register/",
            {
                "first_name": "New",
                "last_name": "User",
                "email": "new@prime.test",
                "password": "LongSecurePassphrase123",
                "invitation_token": invitation.token,
                "accept_terms": True,
                "accept_privacy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["email_verified"])
        user = User.objects.get(email="new@prime.test")
        self.assertTrue(user.is_active)
        self.assertTrue(Membership.objects.filter(user=user, organization=organization, role=Membership.Role.CAPTURE).exists())

    def test_password_reset_request_is_generic_and_reset_is_one_time(self):
        user = User.objects.create_user(
            username="reset@acme.test",
            email="reset@acme.test",
            password="OriginalSecurePassphrase123",
            is_active=True,
        )
        UserSecurityProfile.objects.create(
            user=user,
            lifecycle_status=UserSecurityProfile.LifecycleStatus.ACTIVE,
            email_verified_at=timezone.now(),
        )
        missing = self.client.post("/api/auth/password-reset/request/", {"email": "nobody@acme.test"}, format="json")
        existing = self.client.post("/api/auth/password-reset/request/", {"email": "reset@acme.test"}, format="json")
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(missing.json()["detail"], existing.json()["detail"])
        self.assertEqual(len(mail.outbox), 1)

        token = mail.outbox[0].body.split("token=", 1)[1].strip()
        changed = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": token, "password": "ReplacementSecurePassphrase123"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("ReplacementSecurePassphrase123"))

        replay = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": token, "password": "ThirdSecurePassphrase123"},
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

    def test_security_overview_reports_identity_state(self):
        user = User.objects.create_user(username="secure@acme.test", email="secure@acme.test", password="LongSecurePassphrase123")
        organization = Organization.objects.create(name="Secure Co", slug="secure-co")
        Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)
        UserSecurityProfile.objects.create(
            user=user,
            lifecycle_status=UserSecurityProfile.LifecycleStatus.ACTIVE,
            email_verified_at=timezone.now(),
            terms_accepted_at=timezone.now(),
            terms_version="2026-08-12",
            privacy_accepted_at=timezone.now(),
            privacy_version="2026-08-12",
        )
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/auth/security/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["email_verified"])
        self.assertEqual(response.json()["account_status"], "active")

@override_settings(AXES_ENABLED=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MFAAndSessionSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "LongSecurePassphrase123"
        self.user = User.objects.create_user(username="secure@example.test", email="secure@example.test", password=self.password, is_active=True)
        self.organization = Organization.objects.create(name="Secure Workspace", slug="secure-workspace")
        Membership.objects.create(user=self.user, organization=self.organization, role=Membership.Role.OWNER)
        UserSecurityProfile.objects.create(user=self.user, lifecycle_status=UserSecurityProfile.LifecycleStatus.ACTIVE, email_verified_at=timezone.now())
        self.client = APIClient()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _login(self):
        return self.client.post("/api/auth/login/", {"email": self.user.email, "password": self.password}, format="json")

    def _enable_totp(self):
        import pyotp
        from .security_services import begin_totp_setup, confirm_totp
        setup = begin_totp_setup(self.user)
        ok, codes = confirm_totp(self.user, pyotp.TOTP(setup["secret"]).now())
        self.assertTrue(ok)
        return setup["secret"], codes

    def test_totp_setup_and_confirmation_generate_recovery_codes(self):
        import pyotp
        client = APIClient()
        client.force_authenticate(self.user)
        setup = client.post("/api/auth/security/totp/setup/", {"password": self.password}, format="json")
        self.assertEqual(setup.status_code, 200)
        self.assertIn("provisioning_uri", setup.json())
        confirmed = client.post("/api/auth/security/totp/confirm/", {"code": pyotp.TOTP(setup.json()["secret"]).now()}, format="json")
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(len(confirmed.json()["recovery_codes"]), 10)
        from .models import TOTPDevice
        device = TOTPDevice.objects.get(user=self.user)
        self.assertTrue(device.active)
        self.assertIsNotNone(device.confirmed_at)

    def test_login_requires_totp_after_mfa_is_enabled(self):
        import pyotp
        secret, _ = self._enable_totp()
        first = self._login()
        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.json()["mfa_required"])
        verified = self.client.post("/api/auth/mfa/verify/", {"challenge_token": first.json()["challenge_token"], "method": "totp", "code": pyotp.TOTP(secret).now()}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertIn("forgegov_access", verified.cookies)
        self.assertEqual(self.user.forgegov_auth_sessions.filter(revoked_at__isnull=True).count(), 1)

    def test_recovery_code_is_single_use(self):
        _, codes = self._enable_totp()
        first = self._login()
        verified = self.client.post("/api/auth/mfa/verify/", {"challenge_token": first.json()["challenge_token"], "method": "recovery_code", "code": codes[0]}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.client.cookies.clear()
        second = self._login()
        replay = self.client.post("/api/auth/mfa/verify/", {"challenge_token": second.json()["challenge_token"], "method": "recovery_code", "code": codes[0]}, format="json")
        self.assertEqual(replay.status_code, 400)

    def test_revoked_tracked_session_cannot_continue_using_access_cookie(self):
        from .security_services import revoke_session
        logged_in = self._login()
        self.assertEqual(logged_in.status_code, 200)
        session = self.user.forgegov_auth_sessions.get(revoked_at__isnull=True)
        revoke_session(session)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_step_up_marks_current_session(self):
        logged_in = self._login()
        self.assertEqual(logged_in.status_code, 200)
        response = self.client.post("/api/auth/security/step-up/", {"password": self.password}, format="json")
        self.assertEqual(response.status_code, 200)
        session = self.user.forgegov_auth_sessions.get(revoked_at__isnull=True)
        self.assertIsNotNone(session.step_up_at)

    def test_passkey_registration_options_require_recent_step_up(self):
        logged_in = self._login()
        self.assertEqual(logged_in.status_code, 200)
        blocked = self.client.post("/api/auth/security/passkeys/register/options/", {}, format="json")
        self.assertEqual(blocked.status_code, 403)
        self.client.post("/api/auth/security/step-up/", {"password": self.password}, format="json")
        allowed = self.client.post("/api/auth/security/passkeys/register/options/", {}, format="json")
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("challenge_token", allowed.json())
        self.assertIn("options", allowed.json())

    def test_company_cannot_require_mfa_until_all_members_enroll(self):
        second = User.objects.create_user(username="member@example.test", email="member@example.test", password=self.password, is_active=True)
        Membership.objects.create(user=second, organization=self.organization, role=Membership.Role.VIEWER)
        UserSecurityProfile.objects.create(user=second, lifecycle_status=UserSecurityProfile.LifecycleStatus.ACTIVE, email_verified_at=timezone.now())
        logged_in = self._login()
        self.assertEqual(logged_in.status_code, 200)
        self.client.post("/api/auth/security/step-up/", {"password": self.password}, format="json")
        response = self.client.patch("/api/auth/security/organization-policy/", {"require_mfa": True}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertIn(second.email, response.json()["members_without_mfa"])

    def test_security_overview_lists_current_session_and_mfa_state(self):
        logged_in = self._login()
        self.assertEqual(logged_in.status_code, 200)
        response = self.client.get("/api/auth/security/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["sessions"]), 1)
        self.assertTrue(response.json()["sessions"][0]["current"])
        self.assertFalse(response.json()["mfa"]["enabled"])

    def test_company_required_mfa_enrollment_happens_before_workspace_session(self):
        import pyotp
        OrganizationSecurityPolicy.objects.create(organization=self.organization, require_mfa=True)
        first = self._login()
        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.json()["mfa_enrollment_required"])
        self.assertEqual(self.user.forgegov_auth_sessions.count(), 0)
        setup = self.client.post("/api/auth/mfa/enroll/totp/setup/", {"challenge_token": first.json()["challenge_token"]}, format="json")
        self.assertEqual(setup.status_code, 200)
        confirmed = self.client.post("/api/auth/mfa/enroll/totp/confirm/", {"challenge_token": first.json()["challenge_token"], "code": pyotp.TOTP(setup.json()["secret"]).now()}, format="json")
        self.assertEqual(confirmed.status_code, 200)
        self.assertIn("forgegov_access", confirmed.cookies)
        self.assertEqual(len(confirmed.json()["recovery_codes"]), 10)


class MultiTenantSecurityHardeningTests(TestCase):
    """Hostile cross-company tests for the v3.0.4 release gate."""

    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Defense", slug="alpha-defense")
        self.bravo = Organization.objects.create(name="Bravo Federal", slug="bravo-federal")
        self.charlie = Organization.objects.create(name="Charlie Systems", slug="charlie-systems")

        self.alpha_owner = User.objects.create_user(username="alpha-owner@example.com", email="alpha-owner@example.com", password="StrongPassphrase123!")
        self.alpha_viewer = User.objects.create_user(username="alpha-viewer@example.com", email="alpha-viewer@example.com", password="StrongPassphrase123!")
        self.alpha_proposal = User.objects.create_user(username="alpha-proposal@example.com", email="alpha-proposal@example.com", password="StrongPassphrase123!")
        self.bravo_owner = User.objects.create_user(username="bravo-owner@example.com", email="bravo-owner@example.com", password="StrongPassphrase123!")
        self.bravo_pricing = User.objects.create_user(username="bravo-pricing@example.com", email="bravo-pricing@example.com", password="StrongPassphrase123!")
        self.bravo_contributor = User.objects.create_user(username="bravo-contributor@example.com", email="bravo-contributor@example.com", password="StrongPassphrase123!")
        self.charlie_owner = User.objects.create_user(username="charlie-owner@example.com", email="charlie-owner@example.com", password="StrongPassphrase123!")

        self.alpha_owner_membership = Membership.objects.create(user=self.alpha_owner, organization=self.alpha, role=Membership.Role.OWNER)
        self.alpha_viewer_membership = Membership.objects.create(user=self.alpha_viewer, organization=self.alpha, role=Membership.Role.VIEWER)
        self.alpha_proposal_membership = Membership.objects.create(user=self.alpha_proposal, organization=self.alpha, role=Membership.Role.PROPOSAL)
        self.bravo_owner_membership = Membership.objects.create(user=self.bravo_owner, organization=self.bravo, role=Membership.Role.OWNER)
        self.bravo_pricing_membership = Membership.objects.create(user=self.bravo_pricing, organization=self.bravo, role=Membership.Role.PRICING)
        self.bravo_contributor_membership = Membership.objects.create(user=self.bravo_contributor, organization=self.bravo, role=Membership.Role.CONTRIBUTOR)
        self.charlie_owner_membership = Membership.objects.create(user=self.charlie_owner, organization=self.charlie, role=Membership.Role.OWNER)

        self.opportunity = Opportunity.objects.create(source_id="v304-shared-opportunity", title="Secure vehicle support", agency="USMC")
        self.bravo_pricing_plan = PricingPlan.objects.create(
            organization=self.bravo,
            opportunity=self.opportunity,
            name="Bravo Internal Price",
            target_profit_percent="18",
            minimum_margin_percent="12",
        )
        self.bravo_proposal = ProposalPlan.objects.create(
            organization=self.bravo,
            opportunity=self.opportunity,
            created_by=self.bravo_owner,
        )
        self.bravo_document = OpportunityDocument.objects.create(
            organization=self.bravo,
            opportunity=self.opportunity,
            file_name="Bravo Internal Capture Notes.pdf",
            source_url="https://example.invalid/bravo-internal.pdf",
            status=OpportunityDocument.Status.READY,
        )
        self.bravo_conversation = AIConversation.objects.create(
            organization=self.bravo,
            opportunity=self.opportunity,
            title="Bravo private strategy",
            visibility=AIConversation.Visibility.INTERNAL,
            created_by=self.bravo_owner,
        )
        AIMessage.objects.create(conversation=self.bravo_conversation, role=AIMessage.Role.USER, content="Bravo confidential strategy")

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_viewer_cannot_read_financial_sensitive_pricing(self):
        response = self.client_for(self.alpha_viewer).get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(actor=self.alpha_viewer, action="security.access_denied").exists())

    def test_proposal_manager_cannot_read_financial_sensitive_pricing(self):
        response = self.client_for(self.alpha_proposal).get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(response.status_code, 403)

    def test_pricing_role_can_read_financial_workspace_but_not_other_tenant_plan(self):
        response = self.client_for(self.bravo_pricing).get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plan"]["name"], "Bravo Internal Price")

        # Alpha has the same public opportunity ID but never resolves Bravo's
        # organization-owned pricing plan.
        alpha_owner_response = self.client_for(self.alpha_owner).get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(alpha_owner_response.status_code, 200)
        self.assertNotEqual(alpha_owner_response.json()["plan"]["name"], "Bravo Internal Price")

    def test_proposal_objects_are_organization_scoped(self):
        # Alpha proposal user can create/read Alpha's proposal state for the same
        # public opportunity, but never Bravo's ProposalPlan.
        response = self.client_for(self.alpha_proposal).get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-execution/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ProposalPlan.objects.filter(organization=self.alpha, opportunity=self.opportunity).exists())
        self.assertEqual(ProposalPlan.objects.filter(organization=self.bravo, opportunity=self.opportunity).count(), 1)

    def test_internal_ai_conversation_never_crosses_tenant_boundary(self):
        response = self.client_for(self.alpha_owner).get("/api/ai/conversations/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        self.assertFalse(any(row.get("id") == self.bravo_conversation.id for row in rows))

    def test_document_intelligence_never_returns_other_company_documents(self):
        response = self.client_for(self.alpha_owner).get(f"/api/ai/opportunities/{self.opportunity.source_id}/documents/")
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertFalse(any(row.get("id") == self.bravo_document.id for row in rows))

    def test_executive_portfolio_is_role_restricted(self):
        denied = self.client_for(self.alpha_viewer).get("/api/reports/portfolio-intelligence/")
        self.assertEqual(denied.status_code, 403)
        allowed = self.client_for(self.alpha_owner).get("/api/reports/portfolio-intelligence/")
        self.assertEqual(allowed.status_code, 200)

    def test_project_room_foreign_id_is_not_discoverable(self):
        room = ProjectRoom.objects.create(owner_organization=self.bravo, name="Bravo Internal Room", created_by=self.bravo_owner)
        ProjectRoomMember.objects.create(project_room=room, membership=self.bravo_owner_membership, role=ProjectRoomMember.Role.MANAGER, added_by=self.bravo_owner)
        response = self.client_for(self.alpha_owner).get(f"/api/project-rooms/{room.id}/notes/")
        self.assertEqual(response.status_code, 404)

    def test_project_room_partner_sees_shared_not_internal_or_pricing_without_grant(self):
        room = ProjectRoom.objects.create(owner_organization=self.alpha, name="Alpha Bravo Teaming", created_by=self.alpha_owner)
        ProjectRoomMember.objects.create(project_room=room, membership=self.alpha_owner_membership, role=ProjectRoomMember.Role.MANAGER, added_by=self.alpha_owner)
        ProjectRoomPartner.objects.create(project_room=room, organization=self.bravo, access_level=ProjectRoomPartner.AccessLevel.PARTNER, can_view_pricing=False)
        internal = ProjectRoomFile.objects.create(project_room=room, name="Alpha internal.xlsx", url="https://example.invalid/internal", visibility=ProjectRoomFile.Visibility.INTERNAL, uploaded_by=self.alpha_owner)
        pricing = ProjectRoomFile.objects.create(project_room=room, name="Alpha pricing.xlsx", url="https://example.invalid/pricing", visibility=ProjectRoomFile.Visibility.PRICING, uploaded_by=self.alpha_owner)
        shared = ProjectRoomFile.objects.create(project_room=room, name="Shared scope.pdf", url="https://example.invalid/shared", visibility=ProjectRoomFile.Visibility.SHARED, uploaded_by=self.alpha_owner)

        response = self.client_for(self.bravo_owner).get(f"/api/project-rooms/{room.id}/files/")
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()}
        self.assertIn(shared.id, ids)
        self.assertNotIn(internal.id, ids)
        self.assertNotIn(pricing.id, ids)

    def test_partner_employee_requires_explicit_room_enrollment(self):
        room = ProjectRoom.objects.create(owner_organization=self.alpha, name="Explicit Partner Membership", created_by=self.alpha_owner)
        ProjectRoomMember.objects.create(project_room=room, membership=self.alpha_owner_membership, role=ProjectRoomMember.Role.MANAGER, added_by=self.alpha_owner)
        ProjectRoomPartner.objects.create(project_room=room, organization=self.bravo, can_comment=True, can_upload=True)
        ProjectRoomNote.objects.create(project_room=room, title="Shared note", body="Allowed only after user enrollment", visibility=ProjectRoomNote.Visibility.SHARED, author=self.alpha_owner)

        denied = self.client_for(self.bravo_contributor).get(f"/api/project-rooms/{room.id}/notes/")
        self.assertEqual(denied.status_code, 404)

        # Bravo's own admin may enroll Bravo employees, but cannot manage Alpha's roster.
        enroll = self.client_for(self.bravo_owner).post(
            f"/api/project-rooms/{room.id}/access/",
            {"kind": "member", "membership": self.bravo_contributor_membership.id, "role": ProjectRoomMember.Role.CONTRIBUTOR},
            format="json",
        )
        self.assertEqual(enroll.status_code, 201)

        allowed = self.client_for(self.bravo_contributor).get(f"/api/project-rooms/{room.id}/notes/")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.json()), 1)

    def test_project_room_pricing_share_requires_explicit_partner_grant(self):
        room = ProjectRoom.objects.create(owner_organization=self.alpha, name="Explicit Pricing Share", created_by=self.alpha_owner)
        ProjectRoomMember.objects.create(project_room=room, membership=self.alpha_owner_membership, role=ProjectRoomMember.Role.MANAGER, added_by=self.alpha_owner)
        partner = ProjectRoomPartner.objects.create(project_room=room, organization=self.bravo, can_view_pricing=True)
        pricing = ProjectRoomFile.objects.create(project_room=room, name="Shared pricing volume.pdf", url="https://example.invalid/shared-pricing", visibility=ProjectRoomFile.Visibility.PRICING, uploaded_by=self.alpha_owner)
        response = self.client_for(self.bravo_owner).get(f"/api/project-rooms/{room.id}/files/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(pricing.id, {row["id"] for row in response.json()})

    def test_non_admin_cannot_manage_project_room_partners(self):
        room = ProjectRoom.objects.create(owner_organization=self.alpha, name="Managed Room", created_by=self.alpha_owner)
        ProjectRoomMember.objects.create(project_room=room, membership=self.alpha_proposal_membership, role=ProjectRoomMember.Role.MANAGER, added_by=self.alpha_owner)
        response = self.client_for(self.alpha_proposal).post(
            f"/api/workflow/project-rooms/{room.id}/partners/",
            {"organization": self.bravo.id, "access_level": "partner"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_membership_role_change_takes_effect_without_new_login(self):
        client = self.client_for(self.alpha_viewer)
        first = client.get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(first.status_code, 403)
        self.alpha_viewer_membership.role = Membership.Role.PRICING
        self.alpha_viewer_membership.save(update_fields=["role", "updated_at"])
        second = client.get(f"/api/pricing/opportunities/{self.opportunity.source_id}/")
        self.assertEqual(second.status_code, 200)

    def test_membership_removal_takes_effect_without_new_login(self):
        client = self.client_for(self.alpha_viewer)
        self.alpha_viewer_membership.active = False
        self.alpha_viewer_membership.save(update_fields=["active", "updated_at"])
        response = client.get("/api/dashboard/summary/")
        self.assertEqual(response.status_code, 403)

    def test_command_summary_redacts_financial_data_for_non_financial_role(self):
        response = self.client_for(self.alpha_proposal).get(f"/api/workflow/opportunities/{self.opportunity.source_id}/command-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["pricing"]["restricted"])
        self.assertIsNone(response.json()["pricing"]["profit"])
        self.assertIsNone(response.json()["pricing"]["margin_percent"])
