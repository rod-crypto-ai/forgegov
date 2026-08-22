from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .competitive_positioning import build_competitive_positioning
from .models import (
    Award,
    CompetitivePositionSnapshot,
    Membership,
    Opportunity,
    Organization,
    OrganizationProfile,
    PipelineItem,
)

User = get_user_model()


class CaptureCompetitivePositioningV313Tests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Capture Test Co", slug="capture-test-co")
        self.user = User.objects.create_user(
            username="capture@example.com",
            email="capture@example.com",
            password="StrongPassphrase123!",
        )
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        OrganizationProfile.objects.create(
            organization=self.org,
            naics_codes=["811310"],
            psc_codes=["J023"],
            capabilities=["Heavy equipment maintenance", "Field service"],
            certifications=["ISO 9001"],
        )
        self.opportunity = Opportunity.objects.create(
            source="sam.gov",
            source_id="v313-position-1",
            solicitation_number="W91TEST-26-R-0013",
            title="Tactical Vehicle Maintenance Support",
            description="Vehicle maintenance and field support services",
            agency="Department of the Army",
            office="Army Test Office",
            naics_code="811310",
            psc_code="J023",
            response_deadline=timezone.now() + timedelta(days=30),
            active=True,
        )
        PipelineItem.objects.create(
            organization=self.org,
            opportunity=self.opportunity,
            owner=self.user,
            stage=PipelineItem.Stage.QUALIFIED,
            next_action="Validate incumbent and customer priorities",
        )
        Award.objects.create(
            source_id="v313-award-incumbent",
            award_number="W91OLD-24-C-0001",
            recipient_name="EXAMPLE INCUMBENT LLC",
            recipient_uei="INCUMBENTUEI",
            awarding_agency="Department of the Army",
            awarding_office="Army Test Office",
            obligated_amount=2500000,
            potential_amount=5000000,
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            naics_code="811310",
            psc_code="J023",
            description="Tactical vehicle maintenance support",
            jurisdiction_level="federal",
        )
        Award.objects.create(
            source_id="v313-award-competitor",
            award_number="W91OLD-23-C-0002",
            recipient_name="COMPETITOR SERVICES INC",
            recipient_uei="COMPETITORUEI",
            awarding_agency="Department of the Army",
            awarding_office="Army Test Office",
            obligated_amount=1200000,
            potential_amount=2000000,
            start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31),
            naics_code="811310",
            psc_code="J023",
            description="Vehicle maintenance field support",
            jurisdiction_level="federal",
        )

    def test_competitive_positioning_builds_agency_and_competitor_evidence(self):
        payload = build_competitive_positioning(organization=self.org, opportunity=self.opportunity)
        self.assertEqual(payload["agency_buying_history"]["award_count"], 2)
        self.assertGreaterEqual(payload["qualification"]["score"], 50)
        self.assertIn(payload["qualification"]["recommendation"], {"qualified", "conditional", "hold"})
        self.assertTrue(payload["win_themes"])
        self.assertEqual(payload["agency_buying_history"]["classification"], "official_historical_award_rollup")
        self.assertTrue(
            all(row["classification"] == "competitive_profile_from_official_awards" for row in payload["competitor_profiles"])
        )
        self.assertIn("not an official bidder list", payload["warnings"][0])

    def test_endpoint_records_workspace_scoped_snapshot(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/ai/opportunities/{self.opportunity.source_id}/competitive-positioning/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get("recorded_snapshot_id"))
        snapshot = CompetitivePositionSnapshot.objects.get(organization=self.org, opportunity=self.opportunity)
        self.assertEqual(snapshot.recorded_by, self.user)
        self.assertTrue(snapshot.agency_profile)
        self.assertTrue(snapshot.win_themes)

    def test_viewer_can_read_but_cannot_record_snapshot(self):
        viewer = User.objects.create_user(username="viewer@example.com", email="viewer@example.com", password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org, user=viewer, role=Membership.Role.VIEWER)
        client = APIClient()
        client.force_authenticate(viewer)
        get_response = client.get(f"/api/ai/opportunities/{self.opportunity.source_id}/competitive-positioning/")
        post_response = client.post(f"/api/ai/opportunities/{self.opportunity.source_id}/competitive-positioning/", {}, format="json")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(post_response.status_code, 403)

    def test_snapshot_history_does_not_cross_company_boundary(self):
        other_org = Organization.objects.create(name="Other Capture Co", slug="other-capture-co")
        CompetitivePositionSnapshot.objects.create(
            organization=other_org,
            opportunity=self.opportunity,
            qualification_score=99,
            recommendation="qualified",
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/ai/opportunities/{self.opportunity.source_id}/competitive-positioning/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["history"], [])

    def test_vendor_intelligence_can_build_profile_from_award_history_without_vendor_row(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/intelligence/vendors/?name=COMPETITOR%20SERVICES%20INC")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "COMPETITOR SERVICES INC")
        self.assertEqual(results[0]["classification"], "vendor_profile_from_official_award_history")
        self.assertGreaterEqual(results[0]["award_count"], 1)
        self.assertGreater(float(results[0]["obligated_amount"]), 0)
        self.assertGreater(float(results[0]["average_award_amount"]), 0)
        self.assertGreaterEqual(results[0]["agency_count"], 1)
        self.assertTrue(results[0]["top_psc"])
        self.assertEqual(results[0]["top_psc"][0]["psc_code"], "J023")
        self.assertTrue(results[0]["top_offices"])
        self.assertEqual(results[0]["top_offices"][0]["awarding_office"], "Army Test Office")

    def test_command_center_includes_competitive_positioning(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/ai/opportunities/{self.opportunity.source_id}/command-center/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("competitive_positioning", payload)
        self.assertIn("agency_buying_history", payload["competitive_positioning"])
        self.assertIn("qualification", payload["competitive_positioning"])
