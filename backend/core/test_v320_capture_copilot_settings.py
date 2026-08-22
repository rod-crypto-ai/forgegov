from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .ai import build_grounding_context
from .models import (
    Award,
    Membership,
    Opportunity,
    OpportunityAnalysis,
    Organization,
    OrganizationProfile,
    PipelineItem,
    Task,
    UserPreference,
)

User = get_user_model()


class CaptureCopilotSettingsV320Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Copilot Test Co", slug="copilot-test-co")
        self.user = User.objects.create_user(
            username="copilot@example.com",
            email="copilot@example.com",
            password="StrongPassphrase123!",
        )
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        OrganizationProfile.objects.create(
            organization=self.org,
            naics_codes=["541330"],
            psc_codes=["R425"],
            capabilities=["Engineering support", "Program management"],
        )
        self.opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="v320-copilot-1",
            solicitation_number="W91TEST-26-R-0320",
            title="Engineering Support Services",
            description="Engineering and program management support",
            agency="Department of the Army",
            office="Army Test Office",
            naics_code="541330",
            psc_code="R425",
            response_deadline=timezone.now() + timedelta(days=28),
            active=True,
        )
        PipelineItem.objects.create(
            organization=self.org,
            opportunity=self.opportunity,
            owner=self.user,
            stage=PipelineItem.Stage.QUALIFIED,
            estimated_value=2501337,
            probability_of_win=55,
            next_action="Validate customer and incumbent",
        )
        Award.objects.create(
            source_id="v320-award-1",
            award_number="W91OLD-25-C-0320",
            recipient_name="HISTORICAL COMPETITOR LLC",
            awarding_agency="Department of the Army",
            awarding_office="Army Test Office",
            obligated_amount=1500000,
            potential_amount=2750000,
            start_date=date(2024, 1, 1),
            end_date=date(2026, 1, 1),
            naics_code="541330",
            psc_code="R425",
            description="Engineering support services",
            jurisdiction_level="federal",
        )

    def api_client(self, user=None):
        client = APIClient()
        client.force_authenticate(user or self.user)
        return client

    def test_settings_preferences_persist_and_validate(self):
        response = self.api_client().patch(
            "/api/settings/preferences/",
            {
                "theme": "dark",
                "density": "compact",
                "reduce_motion": True,
                "sidebar_collapsed": True,
                "ai_response_style": "detailed",
                "ai_live_web_enabled": False,
                "ai_workspace_grounding_enabled": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        pref = UserPreference.objects.get(user=self.user)
        self.assertEqual(pref.theme, UserPreference.Theme.DARK)
        self.assertEqual(pref.density, UserPreference.Density.COMPACT)
        self.assertTrue(pref.reduce_motion)
        self.assertTrue(pref.sidebar_collapsed)
        self.assertEqual(pref.ai_response_style, UserPreference.AIResponseStyle.DETAILED)
        self.assertFalse(pref.ai_live_web_enabled)
        self.assertFalse(pref.ai_workspace_grounding_enabled)

        invalid = self.api_client().patch("/api/settings/preferences/", {"theme": "midnight"}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_preferences_are_user_scoped(self):
        other = User.objects.create_user(username="other@example.com", email="other@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=other, role=Membership.Role.CONTRIBUTOR)
        self.api_client().patch("/api/settings/preferences/", {"theme": "dark"}, format="json")
        response = self.api_client(other).get("/api/settings/preferences/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["theme"], "system")

    def test_workspace_grounding_can_be_excluded(self):
        Task.objects.create(organization=self.org, title="PRIVATE CAPTURE TASK", description="Do not include when grounding is disabled")
        with_workspace, _ = build_grounding_context(self.org, include_workspace=True)
        with_financial, _ = build_grounding_context(self.org, include_workspace=True, include_financial=True)
        without_workspace, _ = build_grounding_context(self.org, include_workspace=False)
        self.assertIn("PRIVATE CAPTURE TASK", with_workspace)
        self.assertNotIn("PRIVATE CAPTURE TASK", without_workspace)
        self.assertNotIn('"estimated_value"', with_workspace)
        self.assertIn('"estimated_value"', with_financial)

    def test_capture_copilot_get_returns_deterministic_posture(self):
        response = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["brief"]["opportunity"]["source_id"], self.opportunity.source_id)
        self.assertIn("recommendation", payload["brief"]["posture"])
        self.assertIn("priority_actions", payload["brief"])
        self.assertIn("competitive", payload["brief"])
        self.assertFalse(payload["brief"]["economics"]["restricted"])
        self.assertGreaterEqual(len(payload["modes"]), 6)

    @patch("core.capture_copilot.ask_ai")
    def test_capture_copilot_post_persists_and_reuses_analysis(self, mocked_ai):
        mocked_ai.return_value = {
            "answer": "Bottom Line\nProceed only after validating the evidence gaps.",
            "sources": [{"label": "[OPP-1]", "type": "opportunity", "title": self.opportunity.title, "url": ""}],
            "model": "test-model",
            "provider": "openai",
        }
        first = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "red_team", "question": "Challenge this pursuit."},
            format="json",
        )
        second = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "red_team", "question": "Challenge this pursuit."},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["cached"])
        self.assertTrue(second.json()["cached"])
        self.assertEqual(mocked_ai.call_count, 1)
        analysis = OpportunityAnalysis.objects.get(
            organization=self.org,
            opportunity=self.opportunity,
            analysis_type=OpportunityAnalysis.AnalysisType.CAPTURE_COPILOT,
        )
        self.assertEqual(analysis.created_by, self.user)
        self.assertEqual(analysis.model, "test-model")

    def test_viewer_can_read_copilot_but_financial_context_is_redacted_and_generate_is_blocked(self):
        viewer = User.objects.create_user(username="viewer320@example.com", email="viewer320@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=viewer, role=Membership.Role.VIEWER)
        get_response = self.api_client(viewer).get(f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/")
        post_response = self.api_client(viewer).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "executive_review"},
            format="json",
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertTrue(get_response.json()["brief"]["economics"]["restricted"])
        self.assertNotIn("expected_value", get_response.json()["brief"]["economics"])
        self.assertEqual(get_response.json()["brief"]["capture_memory"], [])
        self.assertEqual(post_response.status_code, 403)

    @patch("core.capture_copilot.ask_ai")
    def test_non_financial_contributor_prompt_excludes_private_modeled_financial_values(self, mocked_ai):
        contributor = User.objects.create_user(username="contrib320@example.com", email="contrib320@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=contributor, role=Membership.Role.CONTRIBUTOR)
        mocked_ai.return_value = {"answer": "Bottom Line\nProceed with evidence validation.", "sources": [], "model": "test-model"}
        response = self.api_client(contributor).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "executive_review"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        prompt = mocked_ai.call_args.kwargs["message"]
        # The private pipeline estimate must never enter a non-financial AI prompt.
        self.assertNotIn("2501337", prompt)
        # Official historical award dollars are public market intelligence and remain usable.
        self.assertIn("2750000", prompt)
        self.assertIn("1500000", prompt)
        self.assertIn("Financial context is excluded", prompt)
        analysis = OpportunityAnalysis.objects.get(id=response.json()["analysis_id"])
        self.assertFalse(analysis.contains_financial)
        self.assertTrue(analysis.uses_workspace_context)

    @patch("core.capture_copilot.ask_ai")
    def test_copilot_honors_private_workspace_grounding_preference(self, mocked_ai):
        pipeline = PipelineItem.objects.get(organization=self.org, opportunity=self.opportunity)
        pipeline.notes = "PRIVATE-CAPTURE-MARKER-320"
        pipeline.save(update_fields=["notes", "updated_at"])
        UserPreference.objects.update_or_create(
            user=self.user,
            defaults={"ai_workspace_grounding_enabled": False},
        )
        mocked_ai.return_value = {"answer": "Bottom Line\nPublic and derived evidence only.", "sources": [], "model": "test-model"}
        response = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "executive_review", "question": "Review without private workspace context."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        prompt = mocked_ai.call_args.kwargs["message"]
        self.assertNotIn("PRIVATE-CAPTURE-MARKER-320", prompt)
        self.assertIn("Private ForgeGov workspace records were excluded", prompt)
        analysis = OpportunityAnalysis.objects.get(id=response.json()["analysis_id"])
        self.assertFalse(analysis.uses_workspace_context)

    def test_financial_copilot_history_is_hidden_after_role_loses_financial_access(self):
        analysis = OpportunityAnalysis.objects.create(
            organization=self.org,
            opportunity=self.opportunity,
            analysis_type=OpportunityAnalysis.AnalysisType.CAPTURE_COPILOT,
            content="Financial scenario: exact modeled economics",
            sources=[],
            model="test-model",
            input_fingerprint="f" * 64,
            contains_financial=True,
            uses_workspace_context=True,
            created_by=self.user,
        )
        membership = Membership.objects.get(organization=self.org, user=self.user)
        membership.role = Membership.Role.VIEWER
        membership.save(update_fields=["role", "updated_at"])
        response = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["brief"]["economics"]["restricted"])
        self.assertNotIn(analysis.id, [row["id"] for row in response.json()["history"]])
