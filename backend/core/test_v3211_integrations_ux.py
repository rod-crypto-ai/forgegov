import os
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Award, ConnectedApp, Membership, Opportunity, Organization, PipelineItem
from .security_services import encrypt_secret

User = get_user_model()


class IntegrationsSubcontractUXV3211Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Integration Test Co", slug="integration-test-co")
        self.user = User.objects.create_user(username="owner3211@example.com", email="owner3211@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.subnet = Opportunity.objects.create(
            source="sba-subnet",
            source_id="sba-subnet:v3211-example",
            title="Engineering Support Subcontract",
            description="Prime seeks small business engineering and field support.",
            agency="EXAMPLE PRIME LLC",
            office="SBA SUBNet",
            notice_type_raw="Subcontracting Opportunity",
            naics_code="541330",
            response_deadline=timezone.now() + timezone.timedelta(days=20),
            place_of_performance="Texas",
            source_url="https://subnet.sba.gov/example",
            raw_data={
                "prime_contractor": "EXAMPLE PRIME LLC",
                "point_of_contact": "Alex Buyer alex.buyer@example.com 555-555-0199",
                "performance_start": "2026-10-01",
                "source_name": "SBA SUBNet",
            },
        )
        Award.objects.create(
            source_id="v3211-prime-award",
            award_number="W91EXAMPLE-25-C-0100",
            recipient_name="EXAMPLE PRIME LLC",
            awarding_agency="Department of the Army",
            obligated_amount=1200000,
            potential_amount=2300000,
            start_date=date(2025, 1, 1),
            end_date=date(2027, 1, 1),
            naics_code="541330",
            psc_code="R425",
            description="Engineering support services",
            jurisdiction_level="federal",
        )

    def api_client(self, user=None):
        client = APIClient()
        client.force_authenticate(user or self.user)
        return client

    @patch.dict(os.environ, {"MICROSOFT_CLIENT_ID": "client-id", "MICROSOFT_CLIENT_SECRET": "client-secret", "MICROSOFT_TENANT_ID": "organizations"}, clear=False)
    def test_microsoft_connect_uses_pkce_and_never_returns_client_secret(self):
        response = self.api_client().post("/api/integrations/microsoft/connect/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        url = response.json()["authorization_url"]
        self.assertIn("code_challenge=", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("Mail.Send", url)
        self.assertIn("Calendars.ReadWrite", url)
        self.assertIn("ChannelMessage.Send", url)
        self.assertNotIn("client-secret", url)

    @patch.dict(os.environ, {"MICROSOFT_CLIENT_ID": "client-id", "MICROSOFT_CLIENT_SECRET": "client-secret"}, clear=False)
    def test_microsoft_status_is_user_scoped_and_does_not_expose_tokens(self):
        ConnectedApp.objects.create(
            organization=self.org,
            user=self.user,
            provider=ConnectedApp.Provider.MICROSOFT,
            status=ConnectedApp.Status.CONNECTED,
            account_email="owner@microsoft.example",
            scopes=["Mail.Send"],
            access_token_encrypted=encrypt_secret("SECRET ACCESS TOKEN"),
            refresh_token_encrypted=encrypt_secret("SECRET REFRESH TOKEN"),
            token_expires_at=timezone.now() + timezone.timedelta(hours=1),
            connected_at=timezone.now(),
        )
        payload = self.api_client().get("/api/integrations/microsoft/status/").json()
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["account_email"], "owner@microsoft.example")
        self.assertNotIn("access_token", payload)
        self.assertNotIn("refresh_token", payload)

        other = User.objects.create_user(username="other3211@example.com", email="other3211@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=other, role=Membership.Role.CONTRIBUTOR)
        other_payload = self.api_client(other).get("/api/integrations/microsoft/status/").json()
        self.assertFalse(other_payload["connected"])
        self.assertEqual(other_payload["account_email"], "")

    def test_microsoft_status_fails_cleanly_after_workspace_access_is_revoked(self):
        Membership.objects.filter(organization=self.org, user=self.user).update(active=False)
        response = self.api_client().get("/api/integrations/microsoft/status/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("active ForgeGov company workspace", response.json()["detail"])

    def test_viewer_cannot_send_external_microsoft_actions(self):
        viewer = User.objects.create_user(username="viewer3211@example.com", email="viewer3211@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=viewer, role=Membership.Role.VIEWER)
        response = self.api_client(viewer).post("/api/integrations/microsoft/send-mail/", {"to": ["test@example.com"], "subject": "Test", "body": "Test"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Read-only users", response.json()["detail"])

    @patch("core.microsoft_views.complete_authorization")
    def test_microsoft_callback_redirects_back_to_settings(self, complete):
        response = self.client.get("/api/integrations/microsoft/callback/?state=state123&code=code123")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings?microsoft=connected", response.url)
        complete.assert_called_once_with(state="state123", code="code123")

    def test_subcontract_workspace_has_prime_contact_parent_and_capture_context(self):
        response = self.api_client().get(f"/api/live/sba/subnet/{self.subnet.source_id}/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["opportunity"]["prime_contractor"], "EXAMPLE PRIME LLC")
        self.assertEqual(payload["contact"]["email"], "alex.buyer@example.com")
        self.assertEqual(payload["prime"]["award_summary"]["award_count"], 1)
        self.assertEqual(payload["prime"]["award_summary"]["obligated_amount"], 1200000.0)
        self.assertGreaterEqual(len(payload["parent_contract_candidates"]), 1)
        self.assertFalse(payload["pipeline"]["active"])

    def test_subcontract_capture_context_is_workspace_isolated(self):
        other_org = Organization.objects.create(name="Other Integration Co", slug="other-integration-co")
        other_user = User.objects.create_user(username="otherowner3211@example.com", email="otherowner3211@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=other_org, user=other_user, role=Membership.Role.OWNER)
        PipelineItem.objects.create(organization=other_org, opportunity=self.subnet, owner=other_user, stage=PipelineItem.Stage.CAPTURE, probability_of_win=88)
        payload = self.api_client().get(f"/api/live/sba/subnet/{self.subnet.source_id}/").json()
        self.assertFalse(payload["pipeline"]["active"])
        self.assertEqual(payload["pipeline"]["probability_of_win"], 0)

    def test_subcontract_detail_rejects_non_subnet_records(self):
        sam = Opportunity.objects.create(source="sam.gov", source_id="v3211-sam-only", title="Prime solicitation")
        response = self.api_client().get(f"/api/live/sba/subnet/{sam.source_id}/")
        self.assertEqual(response.status_code, 404)
