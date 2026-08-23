from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .live_web import search as live_web_search, status as live_web_status
from .models import (
    Membership,
    Opportunity,
    PipelineItem,
    OpportunityDocument,
    OpportunityDocumentChunk,
    Organization,
    ProposalLibraryEntry,
    ProposalRequirement,
    ProposalSection,
    ProposalSectionRevision,
)

User = get_user_model()


class ProposalAutomationLiveWebV321Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Proposal Automation Co", slug="proposal-automation-co")
        self.user = User.objects.create_user(username="proposal321@example.com", email="proposal321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="v321-proposal-1",
            solicitation_number="W91TEST-26-R-0321",
            title="Program Support Services",
            description="Program support and technical services",
            agency="Department of the Army",
            office="Army Test Office",
            naics_code="541611",
            psc_code="R408",
            response_deadline=timezone.now() + timezone.timedelta(days=35),
            active=True,
        )
        document = OpportunityDocument.objects.create(
            organization=self.org,
            opportunity=self.opportunity,
            file_name="Solicitation.pdf",
            source_url="https://example.test/solicitation.pdf",
            checksum="abc321",
            status=OpportunityDocument.Status.READY,
            page_count=25,
            character_count=25000,
            metadata={"structured_intelligence": {"section_l_detected": True, "section_m_detected": True, "deliverables": ["Monthly report"], "clins": ["0001"]}},
        )
        OpportunityDocumentChunk.objects.create(document=document, ordinal=0, page_number=12, section="Section L", text="The technical volume shall describe the staffing transition and technical approach.")
        OpportunityDocumentChunk.objects.create(document=document, ordinal=1, page_number=18, section="Section M", text="The government will evaluate technical approach, staffing, and past performance.")

    def api_client(self, user=None):
        client = APIClient()
        client.force_authenticate(user or self.user)
        return client

    def test_production_workspace_seeds_volumes_sections_and_traceability(self):
        response = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["volumes"]), 3)
        sections = [section for volume in payload["volumes"] for section in volume["sections"]]
        self.assertGreaterEqual(len(sections), 5)
        technical = next(section for section in sections if section["key"] == "technical-approach")
        self.assertGreaterEqual(len(technical["requirement_links"]), 1)
        self.assertIn("package_validation", payload)

    def test_manual_section_save_records_revision(self):
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        section = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["key"] == "technical-approach")
        response = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{section['id']}/",
            {"content": "Technical approach draft with validated staffing transition.", "status": "drafting", "change_summary": "Initial writer draft"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        revision = ProposalSectionRevision.objects.get(section_id=section["id"])
        self.assertEqual(revision.revision, 1)
        self.assertFalse(revision.ai_generated)
        self.assertIn("validated staffing", revision.content)

    @patch("core.proposal_automation.ask_ai")
    def test_ai_draft_is_evidence_grounded_and_revisioned(self, mocked_ai):
        mocked_ai.return_value = {"answer": "Technical Approach\nWe will execute the staffing transition [DOC-1].", "sources": [], "provider": "openai", "model": "test-model"}
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        section = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["key"] == "technical-approach")
        response = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{section['id']}/draft/",
            {"instruction": "Draft the transition approach.", "persist": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        prompt = mocked_ai.call_args.kwargs["message"]
        web_query = mocked_ai.call_args.kwargs["web_query"]
        self.assertIn("official solicitation evidence", prompt)
        self.assertIn("Section L", prompt)
        self.assertIn("VALIDATION REQUIRED", prompt)
        self.assertIn(self.opportunity.solicitation_number, web_query)
        self.assertNotIn("The technical volume shall describe", web_query)
        revision = ProposalSectionRevision.objects.get(section_id=section["id"])
        self.assertTrue(revision.ai_generated)
        self.assertEqual(revision.model, "test-model")

    def test_pricing_section_is_restricted_for_non_financial_proposal_member(self):
        contributor = User.objects.create_user(username="proposal-contrib321@example.com", email="proposal-contrib321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=contributor, role=Membership.Role.PROPOSAL)
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        pricing = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["section_type"] == "pricing")
        response = self.api_client(contributor).get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/")
        restricted = next(section for volume in response.json()["volumes"] for section in volume["sections"] if section["id"] == pricing["id"])
        self.assertTrue(restricted["restricted"])
        self.assertEqual(restricted["content"], "")
        draft = self.api_client(contributor).post(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{pricing['id']}/draft/", {"persist": True}, format="json")
        self.assertEqual(draft.status_code, 403)
        ProposalLibraryEntry.objects.create(organization=self.org, title="Restricted pricing language", category="pricing", content="PRIVATE PRICING CONTENT", source_section_id=pricing["id"], created_by=self.user)
        restricted_again = self.api_client(contributor).get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        self.assertFalse(any(row["title"] == "Restricted pricing language" for row in restricted_again["library"]))
        create_pricing_library = self.api_client(contributor).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
            {"action": "create_library_entry", "title": "Pricing draft", "category": "pricing", "content": "should stay restricted"},
            format="json",
        )
        self.assertEqual(create_pricing_library.status_code, 403)


    def test_contributor_cannot_approve_sections_or_reusable_library_content(self):
        contributor = User.objects.create_user(username="writer321@example.com", email="writer321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=contributor, role=Membership.Role.CONTRIBUTOR)
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        technical = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["key"] == "technical-approach")
        approve = self.api_client(contributor).patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{technical['id']}/",
            {"status": "approved"},
            format="json",
        )
        self.assertEqual(approve.status_code, 403)
        create = self.api_client(contributor).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
            {"action": "create_library_entry", "title": "Writer language", "category": "technical", "content": "Draft reusable language."},
            format="json",
        )
        self.assertEqual(create.status_code, 200)
        entry = ProposalLibraryEntry.objects.get(organization=self.org, title="Writer language")
        approve_entry = self.api_client(contributor).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
            {"action": "update_library_entry", "entry_id": entry.id, "status": "approved"},
            format="json",
        )
        self.assertEqual(approve_entry.status_code, 403)

    def test_substantive_edits_invalidate_prior_section_and_library_approval(self):
        contributor = User.objects.create_user(username="editor321@example.com", email="editor321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=contributor, role=Membership.Role.CONTRIBUTOR)
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        technical = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["key"] == "technical-approach")
        approved = self.api_client().patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{technical['id']}/",
            {"content": "Approved technical content.", "status": "approved"},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)
        edited = self.api_client(contributor).patch(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-sections/{technical['id']}/",
            {"content": "Writer changed the approved content."},
            format="json",
        )
        self.assertEqual(edited.status_code, 200)
        section = ProposalSection.objects.get(pk=technical["id"])
        self.assertEqual(section.status, ProposalSection.Status.DRAFTING)
        self.assertIsNone(section.approved_at)
        entry = ProposalLibraryEntry.objects.create(organization=self.org, title="Approved library text", category="technical", content="Approved reusable copy.", status=ProposalLibraryEntry.Status.APPROVED, approved_by=self.user, approved_at=timezone.now(), created_by=self.user)
        library_edit = self.api_client(contributor).post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
            {"action": "update_library_entry", "entry_id": entry.id, "content": "Edited reusable copy."},
            format="json",
        )
        self.assertEqual(library_edit.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.status, ProposalLibraryEntry.Status.DRAFT)
        self.assertIsNone(entry.approved_at)

    def test_pricing_traceability_is_hidden_from_non_financial_proposal_member(self):
        proposal_user = User.objects.create_user(username="proposal-no-fin321@example.com", email="proposal-no-fin321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=proposal_user, role=Membership.Role.PROPOSAL)
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        pricing = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["section_type"] == "pricing")
        requirement = ProposalRequirement.objects.filter(plan__organization=self.org).first()
        if requirement:
            self.api_client().post(
                f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
                {"action": "link_requirement", "section_id": pricing["id"], "requirement_id": requirement.id},
                format="json",
            )
        restricted = self.api_client(proposal_user).get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        restricted_pricing = next(section for volume in restricted["volumes"] for section in volume["sections"] if section["id"] == pricing["id"])
        self.assertTrue(restricted_pricing["restricted"])
        self.assertEqual(restricted_pricing["requirement_links"], [])
        if requirement:
            link = self.api_client(proposal_user).post(
                f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
                {"action": "link_requirement", "section_id": pricing["id"], "requirement_id": requirement.id},
                format="json",
            )
            self.assertEqual(link.status_code, 403)

    def test_library_entries_are_company_scoped(self):
        workspace = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/").json()
        technical = next(section for volume in workspace["volumes"] for section in volume["sections"] if section["key"] == "technical-approach")
        create = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-production/",
            {"action": "create_library_entry", "title": "Approved transition language", "category": "technical", "content": "Validated company transition language.", "source_section_id": technical["id"]},
            format="json",
        )
        self.assertEqual(create.status_code, 200)
        self.assertEqual(ProposalLibraryEntry.objects.filter(organization=self.org).count(), 1)
        other_org = Organization.objects.create(name="Other Proposal Co", slug="other-proposal-co")
        other_user = User.objects.create_user(username="other321@example.com", email="other321@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=other_org, user=other_user, role=Membership.Role.OWNER)
        other_opp = Opportunity.objects.create(source="sam.gov", source_id="other-v321", title="Other", active=True)
        other_payload = self.api_client(other_user).get(f"/api/ai/opportunities/{other_opp.source_id}/proposal-production/").json()
        self.assertEqual(other_payload["library"], [])

    def test_package_validation_blocks_unapproved_sections(self):
        response = self.api_client().get(f"/api/ai/opportunities/{self.opportunity.source_id}/proposal-package-validation/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready"])
        self.assertTrue(any("section" in row.lower() for row in response.json()["blockers"]))

    @patch("core.capture_copilot.ask_ai")
    def test_capture_copilot_web_query_uses_public_metadata_not_private_workspace_notes(self, mocked_ai):
        PipelineItem.objects.create(organization=self.org, opportunity=self.opportunity, notes="PRIVATE-CAPTURE-SECRET-321", estimated_value=9876543)
        mocked_ai.return_value = {"answer": "Capture review", "sources": [], "provider": "openai", "model": "test-model"}
        response = self.api_client().post(
            f"/api/ai/opportunities/{self.opportunity.source_id}/capture-copilot/",
            {"mode": "executive_review", "refresh": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        web_query = mocked_ai.call_args.kwargs["web_query"]
        self.assertIn(self.opportunity.solicitation_number, web_query)
        self.assertIn(self.opportunity.agency, web_query)
        self.assertNotIn("PRIVATE-CAPTURE-SECRET-321", web_query)
        self.assertNotIn("9876543", web_query)

    @override_settings(SEARXNG_URL="http://searxng:8080", AI_WEB_SEARCH_ENABLED=True, LIVE_WEB_CACHE_SECONDS=600)
    @patch("core.live_web.resilient_request")
    def test_live_web_normalizes_deduplicates_and_reports_live(self, mocked_request):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": [
            {"title": "Acquisition forecast", "url": "https://agency.gov/forecast#top", "content": "Current forecast"},
            {"title": "Duplicate", "url": "https://agency.gov/forecast#other", "content": "Duplicate result"},
        ]}
        mocked_request.return_value = response
        result = live_web_search("agency acquisition forecast", limit=8)
        self.assertEqual(result["status"], "live")
        self.assertTrue(result["reachable"])
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["url"], "https://agency.gov/forecast")
        health = live_web_status(probe=False)
        self.assertEqual(health["status"], "live")
        self.assertTrue(health["cached_fallback_available"])

    @override_settings(SEARXNG_URL="http://searxng:8080", AI_WEB_SEARCH_ENABLED=True, LIVE_WEB_CACHE_SECONDS=600)
    @patch("core.live_web.resilient_request")
    def test_live_web_uses_cached_results_when_provider_degrades(self, mocked_request):
        first = Mock(); first.status_code = 200; first.raise_for_status.return_value = None; first.json.return_value = {"results": [{"title": "Live result", "url": "https://example.gov/live", "content": "Evidence"}]}
        second = Mock(); second.status_code = 503; second.raise_for_status.side_effect = __import__("requests").HTTPError("503", response=second)
        mocked_request.side_effect = [first, second]
        live = live_web_search("same query", limit=4)
        degraded = live_web_search("same query", limit=4)
        self.assertEqual(live["status"], "live")
        self.assertEqual(degraded["status"], "degraded")
        self.assertTrue(degraded["cache_used"])
        self.assertEqual(degraded["results"][0]["url"], "https://example.gov/live")
