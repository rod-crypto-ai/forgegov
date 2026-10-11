from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    CaptureMilestone,
    CapturePlan,
    Membership,
    Opportunity,
    Organization,
    Pursuit,
    PursuitChange,
    PursuitDecisionSnapshot,
    Task,
    WeeklyCaptureReview,
)
from .tests import AuthenticatedApiTestCase


User = get_user_model()


class CaptureOperationsV325Tests(AuthenticatedApiTestCase):
    def setUp(self):
        super().setUp()
        self.opportunity = Opportunity.objects.create(
            source_id="v325-opp",
            title="Enterprise mission support",
            agency="Department of the Navy",
        )
        self.pursuit = Pursuit.objects.create(
            organization=self.organization,
            opportunity=self.opportunity,
            title="Enterprise mission support",
            stage=Pursuit.Stage.QUALIFY,
            owner=self.user,
            estimated_value=1_000_000,
            probability_of_win=40,
            due_date=timezone.now() + timedelta(days=7),
            next_action="Complete the bid review",
        )

    def test_operations_requires_authentication(self):
        response = APIClient().get("/api/capture/operations/")
        self.assertEqual(response.status_code, 401)

    def test_summary_uses_documented_canonical_metrics(self):
        response = self.client.get("/api/capture/operations/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["active_pursuits"], 1)
        self.assertEqual(float(payload["summary"]["pipeline_value"]), 1_000_000)
        self.assertEqual(float(payload["summary"]["weighted_pipeline"]), 400_000)
        self.assertIn("estimated value multiplied", payload["definitions"]["weighted_pipeline"])

    def test_due_soon_excludes_overdue_pursuits(self):
        self.pursuit.due_date = timezone.now() - timedelta(days=1)
        self.pursuit.save(update_fields=["due_date", "updated_at"])
        payload = self.client.get("/api/capture/operations/").json()
        self.assertEqual(payload["summary"]["overdue"], 1)
        self.assertEqual(payload["summary"]["due_within_14_days"], 0)

    def test_template_creates_ordered_dependency_milestones(self):
        response = self.client.post("/api/capture/operations/", {
            "action": "apply_template", "pursuit_id": self.pursuit.id, "template_key": "standard",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        plan = CapturePlan.objects.get(pursuit=self.pursuit, organization=self.organization)
        milestones = list(plan.milestones.order_by("position"))
        self.assertEqual(len(milestones), 6)
        self.assertIsNone(milestones[0].depends_on_id)
        self.assertEqual(milestones[1].depends_on_id, milestones[0].id)

    def test_milestone_dependency_is_enforced(self):
        plan = CapturePlan.objects.create(organization=self.organization, pursuit=self.pursuit, created_by=self.user)
        first = CaptureMilestone.objects.create(organization=self.organization, plan=plan, title="First", position=1)
        second = CaptureMilestone.objects.create(organization=self.organization, plan=plan, title="Second", position=2, depends_on=first)
        response = self.client.post("/api/capture/operations/", {
            "action": "complete_milestone", "milestone_id": second.id, "complete": True,
        }, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(CaptureMilestone.objects.get(pk=second.id).completed_at)

    def test_capture_plan_narrative_is_workspace_scoped_and_editable(self):
        plan = CapturePlan.objects.create(organization=self.organization, pursuit=self.pursuit, created_by=self.user)
        response = self.client.post("/api/capture/operations/", {
            "action": "update_plan", "plan_id": plan.id,
            "objective": "Win and perform safely", "customer_need": "Mission continuity",
            "win_strategy": "Evidence-led transition", "key_risks": ["Staffing lead time"],
        }, format="json")
        self.assertEqual(response.status_code, 200)
        plan.refresh_from_db()
        self.assertEqual(plan.objective, "Win and perform safely")
        self.assertEqual(plan.key_risks, ["Staffing lead time"])

    def test_stage_gate_blocks_incomplete_bid_review(self):
        self.pursuit.stage = Pursuit.Stage.BID_DECISION
        self.pursuit.save(update_fields=["stage", "updated_at"])
        response = self.client.post("/api/capture/operations/", {
            "action": "transition", "pursuit_id": self.pursuit.id, "stage": Pursuit.Stage.CAPTURE,
        }, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(any("bid / no-bid" in row for row in response.json()["findings"]))

    def test_governed_transition_records_immutable_history(self):
        self.pursuit.stage = Pursuit.Stage.BID_DECISION
        self.pursuit.save(update_fields=["stage", "updated_at"])
        PursuitDecisionSnapshot.objects.create(
            organization=self.organization,
            opportunity=self.opportunity,
            recommendation="bid",
            win_probability=55,
            confidence=70,
            evidence_coverage=80,
            recorded_by=self.user,
        )
        response = self.client.post("/api/capture/operations/", {
            "action": "transition", "pursuit_id": self.pursuit.id, "stage": Pursuit.Stage.CAPTURE,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        change = PursuitChange.objects.get(pursuit=self.pursuit)
        self.assertEqual((change.previous_stage, change.new_stage), (Pursuit.Stage.BID_DECISION, Pursuit.Stage.CAPTURE))
        self.assertEqual(change.source, "stage_gate")

    def test_standard_pursuit_edit_records_probability_history(self):
        response = self.client.patch(f"/api/pursuits/{self.pursuit.id}/", {
            "probability_of_win": 60, "change_reason": "Customer meeting completed",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        change = PursuitChange.objects.get(pursuit=self.pursuit)
        self.assertEqual((change.previous_probability, change.new_probability), (40, 60))
        self.assertEqual(change.reason, "Customer meeting completed")

    def test_weekly_review_is_idempotent_per_workspace_and_week(self):
        for notes in ("First review", "Updated review"):
            response = self.client.post("/api/capture/operations/", {
                "action": "record_weekly_review", "notes": notes, "complete": True,
            }, format="json")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(WeeklyCaptureReview.objects.filter(organization=self.organization).count(), 1)
        self.assertEqual(WeeklyCaptureReview.objects.get(organization=self.organization).notes, "Updated review")

    def test_tenant_workload_and_capture_records_are_isolated(self):
        foreign_user = User.objects.create_user(username="foreign-v325@example.com", password="StrongPass!234")
        foreign_org = Organization.objects.create(name="Foreign v325", slug="foreign-v325")
        Membership.objects.create(user=foreign_user, organization=foreign_org, role=Membership.Role.OWNER)
        foreign_pursuit = Pursuit.objects.create(organization=foreign_org, title="Secret pursuit", owner=foreign_user)
        Task.objects.create(organization=foreign_org, title="Secret task", assigned_to=foreign_user)
        response = self.client.post("/api/capture/operations/", {
            "action": "apply_template", "pursuit_id": foreign_pursuit.id, "template_key": "standard",
        }, format="json")
        self.assertEqual(response.status_code, 404)
        payload = self.client.get("/api/capture/operations/").json()
        self.assertNotIn("Secret pursuit", [row["title"] for row in payload["pursuits"]])
        self.assertNotIn("foreign-v325@example.com", [row["owner_name"] for row in payload["workload"]])

    def test_viewer_can_read_but_cannot_change_capture_operations(self):
        viewer = User.objects.create_user(username="viewer-v325@example.com", password="StrongPass!234")
        Membership.objects.create(user=viewer, organization=self.organization, role=Membership.Role.VIEWER)
        client = APIClient()
        client.force_authenticate(viewer)
        self.assertEqual(client.get("/api/capture/operations/").status_code, 200)
        response = client.post("/api/capture/operations/", {"action": "record_weekly_review", "notes": "No"}, format="json")
        self.assertEqual(response.status_code, 403)
