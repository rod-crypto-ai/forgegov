from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from .ai import OpenAIIntegrationError, build_grounding_context
from .forgeai_platform import request_fingerprint
from .models import (
    AIConversation,
    AIMessage,
    CapturePlan,
    ForgeAIResearchRun,
    Membership,
    Opportunity,
    OpportunityWorkspace,
    Organization,
    OrganizationProfile,
    ProposalPlan,
    Pursuit,
)
from .tests import AuthenticatedApiTestCase


User = get_user_model()


class ForgeAIPlatformV326Tests(AuthenticatedApiTestCase):
    def setUp(self):
        super().setUp()
        self.opportunity = Opportunity.objects.create(
            source_id="v326-opportunity",
            title="Mission analytics support",
            agency="Department of the Air Force",
            source="sam.gov",
            source_url="https://sam.gov/opp/v326-opportunity/view",
            active=True,
        )

    def successful_result(self):
        return {
            "answer": "Verified Evidence\nMission analytics support is stored [OPP-1].\n\nAnalysis and Inferences\nFit requires validation.",
            "model": "test-model",
            "provider": "openai",
            "response_id": "resp-v326",
            "request_id": "req-v326",
            "usage": {"input_tokens": 120, "output_tokens": 40},
            "sources": [
                {"label": "[OPP-1]", "type": "opportunity", "title": self.opportunity.title, "url": self.opportunity.source_url, "classification": "official"},
                {"label": "[COMPANY-1]", "type": "company_profile", "title": self.organization.name, "url": "", "classification": "workspace"},
            ],
            "web_enabled": False,
            "web_configured": True,
            "web_status": "unavailable",
        }

    def test_platform_requires_authentication(self):
        response = APIClient().get("/api/ai/platform/")
        self.assertEqual(response.status_code, 401)

    @patch("core.views.ask_ai")
    def test_persisted_chat_records_provenance_and_evidence_summary(self, mocked_ai):
        mocked_ai.return_value = self.successful_result()
        response = self.client.post("/api/ai/chat/", {
            "message": "Assess this opportunity",
            "workflow": "opportunity",
            "persist": True,
            "history": [],
        }, format="json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"], "opportunity")
        self.assertEqual(payload["evidence_summary"]["source_count"], 2)
        self.assertTrue(payload["evidence_summary"]["has_official_or_stored_evidence"])
        self.assertTrue(payload["evidence_summary"]["has_workspace_evidence"])
        run = ForgeAIResearchRun.objects.get(pk=payload["research_run_id"])
        self.assertEqual(run.status, ForgeAIResearchRun.Status.SUCCEEDED)
        self.assertEqual(run.provider_response_id, "resp-v326")
        self.assertEqual(run.token_usage["input_tokens"], 120)
        self.assertEqual(run.conversation_id, payload["conversation_id"])
        self.assertEqual(AIMessage.objects.filter(conversation_id=payload["conversation_id"]).count(), 2)
        self.assertEqual(mocked_ai.call_args.kwargs["workflow"], "opportunity")

    @patch("core.views.ask_ai")
    def test_identical_running_request_is_blocked_without_second_provider_call(self, mocked_ai):
        message = "Review the capture posture"
        ForgeAIResearchRun.objects.create(
            organization=self.organization,
            created_by=self.user,
            workflow=ForgeAIResearchRun.Workflow.CAPTURE,
            status=ForgeAIResearchRun.Status.RUNNING,
            request_fingerprint=request_fingerprint(
                organization_id=self.organization.id,
                user_id=self.user.id,
                workflow="capture",
                message=message,
            ),
        )
        response = self.client.post("/api/ai/chat/", {"message": message, "workflow": "capture"}, format="json")
        self.assertEqual(response.status_code, 409)
        mocked_ai.assert_not_called()

    @patch("core.views.ask_ai")
    def test_stale_running_request_is_recovered(self, mocked_ai):
        mocked_ai.return_value = self.successful_result()
        message = "Review stale request recovery"
        stale = ForgeAIResearchRun.objects.create(
            organization=self.organization,
            created_by=self.user,
            workflow=ForgeAIResearchRun.Workflow.RESEARCH,
            request_fingerprint=request_fingerprint(
                organization_id=self.organization.id,
                user_id=self.user.id,
                workflow="research",
                message=message,
            ),
        )
        ForgeAIResearchRun.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(minutes=10))
        response = self.client.post("/api/ai/chat/", {"message": message}, format="json")
        self.assertEqual(response.status_code, 200)
        stale.refresh_from_db()
        self.assertEqual(stale.status, ForgeAIResearchRun.Status.FAILED)
        self.assertEqual(stale.error_code, "stale_run_recovered")

    @patch("core.views.ask_ai")
    def test_provider_failure_closes_run_without_persisting_provider_secrets(self, mocked_ai):
        mocked_ai.side_effect = OpenAIIntegrationError("Provider unavailable", status_code=502)
        response = self.client.post("/api/ai/chat/", {"message": "Try provider"}, format="json")
        self.assertEqual(response.status_code, 502)
        run = ForgeAIResearchRun.objects.get()
        self.assertEqual(run.status, ForgeAIResearchRun.Status.FAILED)
        self.assertEqual(run.error_code, "provider_502")
        self.assertEqual(run.source_manifest, [])
        self.assertNotIn("Provider unavailable", run.error_code)

    def test_grounding_unifies_company_capture_proposal_and_workspace_context(self):
        OrganizationProfile.objects.create(
            organization=self.organization,
            description="Secure analytics delivery",
            capabilities=["data engineering"],
        )
        pursuit = Pursuit.objects.create(
            organization=self.organization,
            opportunity=self.opportunity,
            title="Mission analytics pursuit",
            estimated_value=500000,
            next_action="Validate staffing",
        )
        CapturePlan.objects.create(
            organization=self.organization,
            pursuit=pursuit,
            win_strategy="Use validated transition evidence",
            created_by=self.user,
        )
        OpportunityWorkspace.objects.create(
            organization=self.organization,
            opportunity=self.opportunity,
            capture_summary="Customer continuity matters",
        )
        ProposalPlan.objects.create(
            organization=self.organization,
            opportunity=self.opportunity,
            created_by=self.user,
        )

        context, sources = build_grounding_context(self.organization, include_financial=False)
        self.assertIn("[COMPANY-1]", context)
        self.assertIn("[CAPTURE-1]", context)
        self.assertIn("[WORKSPACE-1]", context)
        self.assertIn("[PROPOSAL-1]", context)
        self.assertNotIn("500000", context)
        self.assertIn("workspace", {source.classification for source in sources})

    def test_grounding_excludes_other_workspace_private_context(self):
        other_user = User.objects.create_user(username="other-v326@example.com", password="StrongPass!234")
        other = Organization.objects.create(name="Other V326", slug="other-v326")
        Membership.objects.create(user=other_user, organization=other, role=Membership.Role.OWNER)
        OrganizationProfile.objects.create(organization=other, description="FOREIGN SECRET CAPABILITY")
        other_pursuit = Pursuit.objects.create(organization=other, title="FOREIGN SECRET PURSUIT")
        CapturePlan.objects.create(organization=other, pursuit=other_pursuit, win_strategy="FOREIGN SECRET STRATEGY")

        context, _ = build_grounding_context(self.organization)
        self.assertNotIn("FOREIGN SECRET", context)

    def test_platform_status_is_workspace_scoped_and_does_not_expose_prompts(self):
        conversation = AIConversation.objects.create(
            organization=self.organization,
            title="Sensitive research question",
            created_by=self.user,
        )
        ForgeAIResearchRun.objects.create(
            organization=self.organization,
            conversation=conversation,
            created_by=self.user,
            workflow="market",
            status=ForgeAIResearchRun.Status.SUCCEEDED,
            request_fingerprint="a" * 64,
            evidence_summary={"source_count": 4},
        )
        other = Organization.objects.create(name="Foreign Platform", slug="foreign-platform")
        ForgeAIResearchRun.objects.create(
            organization=other,
            workflow="research",
            status=ForgeAIResearchRun.Status.SUCCEEDED,
            request_fingerprint="b" * 64,
        )

        response = self.client.get("/api/ai/platform/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["recent_runs"]), 1)
        self.assertEqual(payload["recent_runs"][0]["source_count"], 4)
        self.assertNotIn("Sensitive research question", str(payload["recent_runs"]))
        self.assertTrue(payload["governance"]["human_review_required"])
        self.assertFalse(payload["governance"]["autonomous_record_changes"])

    def test_invalid_workflow_is_rejected_before_provider_execution(self):
        response = self.client.post("/api/ai/chat/", {"message": "Do something", "workflow": "autonomous_agent"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ForgeAIResearchRun.objects.count(), 0)

    def test_conversation_from_another_workspace_cannot_be_reused(self):
        other = Organization.objects.create(name="Foreign Conversation", slug="foreign-conversation")
        conversation = AIConversation.objects.create(organization=other, title="Foreign", created_by=self.user)
        response = self.client.post("/api/ai/chat/", {
            "message": "Continue foreign conversation",
            "conversation_id": conversation.id,
        }, format="json")
        self.assertEqual(response.status_code, 404)
        run = ForgeAIResearchRun.objects.get()
        self.assertEqual(run.status, ForgeAIResearchRun.Status.FAILED)
        self.assertEqual(run.error_code, "conversation_not_found")
