from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from django.test import override_settings

from .integrations import _clean_attachment_name, search_sam_contract_awards, search_sba_subnet_opportunities
from .models import Agency, Invitation, Membership, NetworkConnection, Opportunity, Organization, OrganizationProfile, PipelineItem, ProjectRoom, ProjectRoomInvitation
from .tests import AuthenticatedApiTestCase


class ProductionAuditRemediationTests(AuthenticatedApiTestCase):
    def test_opportunity_only_market_categories_remain_visible(self):
        Opportunity.objects.create(source_id="naics-only", title="Stored opportunity", naics_code="541512", psc_code="DA10")
        naics = self.client.get("/api/intelligence/categories/?type=naics").json()["results"]
        psc = self.client.get("/api/intelligence/categories/?type=psc").json()["results"]
        self.assertEqual(next(row for row in naics if row["code"] == "541512")["opportunity_count"], 1)
        self.assertEqual(next(row for row in psc if row["code"] == "DA10")["opportunity_count"], 1)

    def test_agency_profile_matches_sam_department_abbreviation(self):
        Agency.objects.create(name="Department of Defense")
        Opportunity.objects.create(source_id="dod-active", title="Active DOD requirement", agency="DEPT OF DEFENSE", active=True)
        payload = self.client.get("/api/intelligence/agencies/?q=Department%20of%20Defense").json()
        self.assertEqual(payload["results"][0]["active_opportunities"], 1)

    def test_expired_team_invitation_is_transitioned_and_not_returned(self):
        invitation = Invitation.objects.create(
            organization=self.organization, email=self.user.email, role=Membership.Role.VIEWER,
            token="expired-v3214", expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(self.client.get("/api/auth/invitations/pending/").json(), [])
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.EXPIRED)

    def test_duplicate_company_identity_cannot_connect(self):
        duplicate = Organization.objects.create(name=self.organization.name, slug="test-workspace-duplicate")
        OrganizationProfile.objects.create(organization=duplicate, is_public=True)
        response = self.client.post("/api/network/connections/", {"recipient": duplicate.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NetworkConnection.objects.exists())
        directory = self.client.get("/api/network/directory/").json()
        self.assertEqual(directory["results"], [])

    def test_dashboard_shared_metrics_use_active_pipeline_definition(self):
        active = Opportunity.objects.create(source_id="active-pipeline", title="Active pipeline")
        closed = Opportunity.objects.create(source_id="closed-pipeline", title="Closed pipeline")
        PipelineItem.objects.create(organization=self.organization, opportunity=active, stage="capture", estimated_value=1000, probability_of_win=50)
        PipelineItem.objects.create(organization=self.organization, opportunity=closed, stage="lost", estimated_value=9000, probability_of_win=100)
        payload = self.client.get("/api/dashboard/summary/").json()
        self.assertEqual(payload["pipeline"]["total"], 1)
        self.assertEqual(payload["pursuits"]["total"], 1)
        self.assertEqual(float(payload["pipeline"]["weighted_value"]), 500)

    def test_connector_manager_lists_every_advertised_source(self):
        keys = {row["key"] for row in self.client.get("/api/intelligence/connector-registry/").json()["connectors"]}
        self.assertTrue({"sam-opportunities", "grants-opportunities", "sba-subnet", "federal-forecasts", "usaspending-awards", "usaspending-vehicles", "state-local-directory"}.issubset(keys))

    def test_attachment_filename_uses_official_query_metadata(self):
        self.assertEqual(_clean_attachment_name("", "https://sam.gov/download?filename=Solicitation%20PWS.pdf"), "Solicitation PWS.pdf")

    @patch("core.integrations.resilient_request")
    def test_subnet_second_application_page_requests_and_returns_new_source_pages(self, request):
        def response_for(_source, _method, url, **kwargs):
            source_page = kwargs["params"]["page"]
            response = Mock(url=url, status_code=200)
            response.raise_for_status.return_value = None
            response.text = f"<table><tbody><tr><td><a href='/opportunity/{source_page}'>Listing {source_page}</a> Prime Description</td><td>12/31/2026</td><td>01/01/2027</td><td>TX</td><td>541512</td></tr></tbody></table>"
            return response
        request.side_effect = response_for
        payload = search_sba_subnet_opportunities(page=1, page_size=20)
        requested_pages = [call.kwargs["params"]["page"] for call in request.call_args_list[:2]]
        self.assertEqual(requested_pages, [2, 3])
        self.assertEqual(payload["page"], 1)
        self.assertEqual([row["title"] for row in payload["results"]], ["Listing 2", "Listing 3"])

    def test_expired_project_room_invitation_is_not_counted_pending(self):
        partner = Organization.objects.create(name="Partner", slug="partner")
        room = ProjectRoom.objects.create(name="Room", owner_organization=self.organization, created_by=self.user)
        invitation = ProjectRoomInvitation.objects.create(project_room=room, invited_organization=partner, expires_at=timezone.now()-timedelta(minutes=1))
        Membership.objects.create(user=self.user, organization=partner, role=Membership.Role.OWNER)
        payload = self.client.get("/api/dashboard/command-center/", HTTP_X_FORGEGOV_ORGANIZATION=str(partner.id)).json()
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ProjectRoomInvitation.Status.EXPIRED)
        self.assertEqual(payload["metrics"]["pending_invitations"], 0)

    @override_settings(SAM_GOV_API_KEY="test-key", SAM_CONTRACT_AWARDS_BASE_URL="https://api.sam.gov/awards")
    @patch("core.integrations.resilient_request")
    def test_contract_award_title_has_identifier_fallback(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"totalRecords": 1, "awardSummary": [{"contractId": {"piid": "IDV-123"}, "coreData": {}, "awardDetails": {}}]}
        request.return_value = response
        row = search_sam_contract_awards(record_type="idv")["results"][0]
        self.assertEqual(row["title"], "Contract vehicle IDV-123")
