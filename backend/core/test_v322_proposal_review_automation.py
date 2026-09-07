import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Membership,
    Opportunity,
    OpportunityDocument,
    OpportunityDocumentChunk,
    Organization,
    ProposalFinding,
    ProposalReviewRun,
    ProposalSectionRevision,
)
from .proposal_automation import ensure_proposal_production
from .proposal_review import create_review_run, execute_review_run

User = get_user_model()


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class ProposalReviewAutomationV322Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Review Co", slug="review-co")
        self.owner = User.objects.create_user(username="owner322@example.com")
        Membership.objects.create(
            organization=self.org, user=self.owner, role=Membership.Role.OWNER
        )
        self.contributor = User.objects.create_user(username="writer322@example.com")
        Membership.objects.create(
            organization=self.org,
            user=self.contributor,
            role=Membership.Role.CONTRIBUTOR,
        )
        self.other_org = Organization.objects.create(
            name="Other Review Co", slug="other-review-co"
        )
        self.other = User.objects.create_user(username="other322@example.com")
        Membership.objects.create(
            organization=self.other_org, user=self.other, role=Membership.Role.OWNER
        )
        self.opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="review-322",
            title="Fleet support",
            solicitation_number="W91-322",
            response_deadline=timezone.now() + timezone.timedelta(days=30),
            active=True,
        )
        document = OpportunityDocument.objects.create(
            organization=self.org,
            opportunity=self.opportunity,
            file_name="Solicitation.pdf",
            source_url="https://example.test/solicitation.pdf",
            checksum="review322",
            status=OpportunityDocument.Status.READY,
        )
        self.chunk = OpportunityDocumentChunk.objects.create(
            document=document,
            ordinal=0,
            page_number=8,
            section="Section L",
            text="The offeror shall describe its transition staffing plan.",
        )
        self.plan = ensure_proposal_production(
            organization=self.org, opportunity=self.opportunity, user=self.owner
        )
        self.section = self.plan.volumes.get(
            key="volume-1-technical-management"
        ).sections.get(key="technical-approach")
        self.section.content = "Our transition staffing plan begins at award."
        self.section.save()
        ProposalSectionRevision.objects.create(
            section=self.section,
            revision=1,
            content="Initial plan",
            created_by=self.owner,
        )
        ProposalSectionRevision.objects.create(
            section=self.section,
            revision=2,
            content=self.section.content,
            created_by=self.owner,
        )

    def api_client(self, user=None):
        client = APIClient()
        client.force_authenticate(user or self.owner)
        return client

    def test_review_run_is_deduplicated_for_same_baseline(self):
        first, created = create_review_run(
            organization=self.org,
            opportunity=self.opportunity,
            user=self.owner,
            review_type="compliance",
        )
        second, created_again = create_review_run(
            organization=self.org,
            opportunity=self.opportunity,
            user=self.owner,
            review_type="compliance",
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)

    @patch("core.proposal_review.ask_ai")
    def test_review_creates_scored_evidence_linked_finding(self, mocked_ai):
        mocked_ai.return_value = {
            "provider": "openai",
            "model": "review-test",
            "answer": json.dumps(
                {
                    "summary": "Staffing evidence is incomplete.",
                    "scorecard": [
                        {
                            "criterion": "requirement_coverage",
                            "score": 60,
                            "explanation": "Partial",
                            "confidence": 90,
                        }
                    ],
                    "findings": [
                        {
                            "severity": "high",
                            "title": "Unsupported staffing level",
                            "detail": "No staffing count is supported.",
                            "recommendation": "Add sourced staffing quantities.",
                            "confidence": 88,
                            "section_id": self.section.id,
                            "requirement_id": self.plan.requirements.first().id,
                            "citations": [
                                {
                                    "document_chunk_id": self.chunk.id,
                                    "quotation": "shall describe its transition staffing plan",
                                    "locator": "Section L, page 8",
                                }
                            ],
                        }
                    ],
                }
            ),
        }
        run, _ = create_review_run(
            organization=self.org,
            opportunity=self.opportunity,
            user=self.owner,
            review_type="compliance",
        )
        execute_review_run(run)
        run.refresh_from_db()
        self.assertEqual(run.status, ProposalReviewRun.Status.COMPLETED)
        self.assertEqual(run.model, "review-test")
        finding = ProposalFinding.objects.get(plan=self.plan)
        self.assertEqual(finding.section, self.section)
        self.assertEqual(finding.review_run, run)
        self.assertEqual(finding.evidence_items.get().document_chunk, self.chunk)

    def test_review_center_is_tenant_scoped(self):
        response = self.api_client(self.other).get(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-review-center/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runs"], [])

    @patch("core.tasks.execute_proposal_review.delay")
    def test_review_endpoint_queues_background_task(self, delay):
        response = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-review-center/",
            {"review_type": "red"},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        delay.assert_called_once()

    def test_revision_comparison_requires_same_tenant_and_section(self):
        revisions = list(self.section.revisions.order_by("revision"))
        response = self.api_client().get(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{self.section.id}/compare/?older={revisions[0].id}&newer={revisions[1].id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["changed"])
        self.assertIn("+Our transition", "\n".join(response.json()["diff"]))
        denied = self.api_client(self.other).get(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{self.section.id}/compare/?older={revisions[0].id}&newer={revisions[1].id}"
        )
        self.assertEqual(denied.status_code, 404)

    def test_contributor_cannot_pass_review_gate_or_accept_risk(self):
        review = self.plan.reviews.get(review_type="red")
        blocked = self.api_client(self.contributor).patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-reviews/{review.id}/",
            {"status": "passed"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 403)
        finding = ProposalFinding.objects.create(
            plan=self.plan, review=review, title="Risk", created_by=self.owner
        )
        accepted = self.api_client(self.contributor).patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-findings/{finding.id}/",
            {"status": "accepted", "resolution_response": "Accept"},
            format="json",
        )
        self.assertEqual(accepted.status_code, 403)

    def test_resolution_requires_justification_and_records_comment(self):
        finding = ProposalFinding.objects.create(
            plan=self.plan, title="Gap", created_by=self.owner
        )
        invalid = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-findings/{finding.id}/",
            {"status": "resolved"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        valid = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-findings/{finding.id}/",
            {"status": "resolved", "resolution_response": "Added Section L citation."},
            format="json",
        )
        self.assertEqual(valid.status_code, 200)
        finding.refresh_from_db()
        self.assertEqual(finding.resolved_by, self.owner)
        self.assertTrue(finding.comments.get().resolution_event)

    def test_open_finding_prevents_review_gate_pass(self):
        review = self.plan.reviews.get(review_type="red")
        ProposalFinding.objects.create(
            plan=self.plan, review=review, title="Unresolved gap", created_by=self.owner
        )
        response = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-reviews/{review.id}/",
            {"status": "passed"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_content_change_reopens_findings_and_review_gate(self):
        review = self.plan.reviews.get(review_type="red")
        review.status = "passed"
        review.completed_at = timezone.now()
        review.gate_decision_by = self.owner
        review.gate_decision_at = timezone.now()
        review.save()
        finding = ProposalFinding.objects.create(
            plan=self.plan,
            review=review,
            section=self.section,
            title="Previously fixed",
            status="resolved",
            resolution_response="Old correction",
            resolved_by=self.owner,
            resolved_at=timezone.now(),
            created_by=self.owner,
        )
        response = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{self.section.id}/",
            {
                "content": "Materially revised technical approach.",
                "change_summary": "Rewrite",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        finding.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(finding.status, "open")
        self.assertEqual(finding.resolution_response, "")
        self.assertEqual(review.status, "in_progress")
        self.assertIsNone(review.gate_decision_by)
