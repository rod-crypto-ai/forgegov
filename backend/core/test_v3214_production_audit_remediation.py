from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from django.test import override_settings

from .integrations import _clean_attachment_name, search_grants_opportunities, search_sam_contract_awards, search_sba_subnet_opportunities, search_usaspending_contract_vehicles
from .intelligence.services.award_ingestion import connector_registry_payload
from .models import Agency, CollaborationNotification, Invitation, Membership, NetworkConnection, Opportunity, Organization, OrganizationProfile, PipelineItem, ProjectRoom, ProjectRoomInvitation, Pursuit
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

    def test_dashboard_separates_pipeline_and_pursuit_definitions(self):
        active = Opportunity.objects.create(source_id="active-pipeline", title="Active pipeline")
        closed = Opportunity.objects.create(source_id="closed-pipeline", title="Closed pipeline")
        PipelineItem.objects.create(organization=self.organization, opportunity=active, stage="capture", estimated_value=1000, probability_of_win=50)
        PipelineItem.objects.create(organization=self.organization, opportunity=closed, stage="lost", estimated_value=9000, probability_of_win=100)
        Pursuit.objects.create(organization=self.organization, opportunity=active, title="Active pursuit", stage=Pursuit.Stage.PROPOSAL, estimated_value=2000, probability_of_win=75)
        Pursuit.objects.create(organization=self.organization, opportunity=closed, title="Closed pursuit", stage=Pursuit.Stage.LOST, estimated_value=9000, probability_of_win=100)
        payload = self.client.get("/api/dashboard/summary/").json()
        self.assertEqual(payload["pipeline"]["total"], 1)
        self.assertEqual(payload["pursuits"]["total"], 1)
        self.assertEqual(float(payload["pipeline"]["weighted_value"]), 500)
        self.assertEqual(float(payload["pursuits"]["weighted_value"]), 1500)

    def test_admin_invitation_list_expires_old_pending_rows(self):
        invitation = Invitation.objects.create(
            organization=self.organization, email="expired@example.com", role=Membership.Role.VIEWER,
            token="expired-admin-list", expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.get("/api/team/invitations/")
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, Invitation.Status.EXPIRED)

    def test_collaboration_notification_filters_unread_and_intelligence_copies(self):
        CollaborationNotification.objects.create(organization=self.organization, user=self.user, title="Alert copy", kind="intelligence_new_opportunity", read=False)
        CollaborationNotification.objects.create(organization=self.organization, user=self.user, title="Project update", kind="project_room", read=False)
        CollaborationNotification.objects.create(organization=self.organization, user=self.user, title="Read update", kind="project_room", read=True)
        payload = self.client.get("/api/collaboration/notifications/?read=false&exclude_intelligence=true").json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["title"], "Project update")

    def test_global_search_deduplicates_duplicate_opportunity_records(self):
        Opportunity.objects.create(source_id="duplicate-a", title="Shared search result", solicitation_number="SOL-1")
        Opportunity.objects.create(source_id="duplicate-b", title="Shared search result", solicitation_number="SOL-1")
        payload = self.client.get("/api/intelligence/search/?q=Shared%20search").json()
        matches = [row for row in payload["results"] if row["type"] == "opportunity"]
        self.assertEqual(len(matches), 1)

    def test_unprobed_connector_registry_does_not_claim_current_health(self):
        payload = connector_registry_payload(probe=False)
        self.assertTrue(payload["connectors"])
        self.assertTrue(all(row["status"] == "not_verified" for row in payload["connectors"]))
        self.assertEqual(payload["summary"]["healthy"], 0)

    @patch("core.integrations.resilient_request")
    def test_grants_search_decodes_html_entities(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"errorcode": 0, "data": {"hitCount": 1, "oppHits": [{"id": 123, "title": "Alpha &ndash; Beta", "synopsisDesc": "One &amp; two"}]}}
        request.return_value = response
        row = search_grants_opportunities()["opportunities"][0]
        self.assertEqual(row["title"], "Alpha – Beta")
        self.assertEqual(row["description"], "One & two")

    @patch("core.integrations.resilient_request")
    def test_vehicle_keyword_excludes_visibly_irrelevant_rows(self, request):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"results": [
            {"Award ID": "A", "Description": "Logistics support vehicle", "Recipient Name": "Alpha"},
            {"Award ID": "B", "Description": "Medical laboratory services", "Recipient Name": "Beta"},
        ], "page_metadata": {"hasNext": False}}
        request.return_value = response
        rows = search_usaspending_contract_vehicles(keyword="logistics")["results"]
        self.assertEqual([row["Award ID"] for row in rows], ["A"])

    def test_connector_manager_lists_every_advertised_source(self):
        keys = {row["key"] for row in self.client.get("/api/intelligence/connector-registry/").json()["connectors"]}
        self.assertTrue({"sam-opportunities", "grants-opportunities", "sba-subnet", "federal-forecasts", "usaspending-awards", "usaspending-vehicles", "state-local-directory"}.issubset(keys))

    def test_attachment_filename_uses_official_query_metadata(self):
        self.assertEqual(_clean_attachment_name("", "https://sam.gov/download?filename=Solicitation%20PWS.pdf"), "Solicitation PWS.pdf")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
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
