from unittest.mock import Mock, patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .integrations import _build_sam_params, search_sam_opportunities, upsert_sam_opportunity
from .models import Invitation, Membership, Opportunity, Organization, PipelineItem

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
        self.assertEqual(response.json()["version"], "1.0.2")


class RouterRegressionTests(TestCase):
    def test_router_names_are_registered(self):
        self.assertEqual(reverse("organization-list"), "/api/organizations/")
        self.assertEqual(reverse("pipeline-item-list"), "/api/pipeline/")
        self.assertEqual(reverse("task-list"), "/api/tasks/")
        self.assertEqual(reverse("saved-search-list"), "/api/saved-searches/")
        self.assertEqual(reverse("contact-group-list"), "/api/contact-groups/")


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
