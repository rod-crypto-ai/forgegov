from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Award, Contact, Membership, NetworkConnection, Opportunity, Organization, OrganizationProfile, Vendor
from .tests import AuthenticatedApiTestCase


User = get_user_model()


class MarketCompetitorIntelligenceV324Tests(AuthenticatedApiTestCase):
    def setUp(self):
        super().setUp()
        OrganizationProfile.objects.create(
            organization=self.organization,
            capabilities=["Program management"],
            naics_codes=["541512"],
            psc_codes=["DA10"],
        )
        self.other = Organization.objects.create(name="Qualified Partner", slug="qualified-partner")
        OrganizationProfile.objects.create(
            organization=self.other,
            capabilities=["Cybersecurity", "Cloud migration"],
            naics_codes=["541512"],
            psc_codes=["DA10"],
            contract_vehicles=["GSA MAS"],
            state="VA",
            is_public=True,
            accepting_partners=True,
            verified=True,
        )
        Vendor.objects.create(name="ALPHA SYSTEMS LLC", uei="ALPHAUEI", cage_code="A1B2C", state="VA")
        Vendor.objects.create(name="BETA TECHNOLOGY INC", uei="BETAUEI", cage_code="B1C2D", state="TX")
        Award.objects.create(
            source_id="v324-alpha-contract", award_number="W91-ALPHA", recipient_name="ALPHA SYSTEMS LLC",
            recipient_uei="ALPHAUEI", recipient_cage="A1B2C", awarding_agency="Department of the Army",
            awarding_office="Army Contracting Command", obligated_amount=2_000_000, potential_amount=4_000_000,
            start_date=date(2025, 1, 1), end_date=date(2027, 1, 1), naics_code="541512", psc_code="DA10",
            description="Cloud systems modernization support", source_updated_at=timezone.now(),
        )
        Award.objects.create(
            source_id="v324-alpha-vehicle", award_number="GS-MAS-ALPHA", recipient_name="ALPHA SYSTEMS LLC",
            recipient_uei="ALPHAUEI", awarding_agency="General Services Administration", obligated_amount=500_000,
            potential_amount=10_000_000, start_date=date(2024, 1, 1), end_date=date(2028, 1, 1),
            naics_code="541512", psc_code="DA10", award_type=Award.AwardType.VEHICLE,
        )
        Award.objects.create(
            source_id="v324-beta-contract", award_number="W91-BETA", recipient_name="BETA TECHNOLOGY INC",
            recipient_uei="BETAUEI", awarding_agency="Department of the Army", obligated_amount=1_000_000,
            potential_amount=1_500_000, start_date=date(2023, 1, 1), end_date=date(2024, 1, 1),
            naics_code="541512", psc_code="DA10", description="Legacy application operations",
        )

    def test_vendor_dossier_scopes_private_contacts_to_active_workspace(self):
        Contact.objects.create(organization=self.organization, full_name="Visible Contact", email="visible@example.com", vendor_name="ALPHA SYSTEMS LLC")
        foreign_user = User.objects.create_user(username="foreign@example.com", password="StrongPass!234")
        foreign_org = Organization.objects.create(name="Foreign Workspace", slug="foreign-workspace")
        Membership.objects.create(user=foreign_user, organization=foreign_org, role=Membership.Role.OWNER)
        Contact.objects.create(organization=foreign_org, full_name="Secret Contact", email="secret@example.com", vendor_name="ALPHA SYSTEMS LLC")

        payload = self.client.get("/api/intelligence/market/vendors/dossier/?name=ALPHA%20SYSTEMS%20LLC").json()

        self.assertEqual([row["email"] for row in payload["contacts"]], ["visible@example.com"])
        legacy = self.client.get("/api/intelligence/vendors/?name=ALPHA%20SYSTEMS%20LLC").json()
        self.assertEqual([row["email"] for row in legacy["results"][0]["contacts"]], ["visible@example.com"])

    def test_vendor_dossier_uses_uei_and_reports_official_evidence(self):
        payload = self.client.get("/api/intelligence/market/vendors/dossier/?uei=ALPHAUEI").json()
        self.assertEqual(payload["identity"]["name"], "ALPHA SYSTEMS LLC")
        self.assertEqual(payload["metrics"]["award_count"], 2)
        self.assertEqual(payload["evidence"]["classification"], "forgegov_rollup_of_official_awards")

    def test_vendor_name_normalization_matches_legal_suffix_variants(self):
        payload = self.client.get("/api/intelligence/market/vendors/dossier/?name=ALPHA%20SYSTEMS%20INC").json()
        self.assertEqual(payload["metrics"]["award_count"], 2)

    def test_vendor_comparison_is_bounded_and_consistent(self):
        response = self.client.get("/api/intelligence/market/vendors/compare/?vendors=ALPHA%20SYSTEMS%20LLC|BETA%20TECHNOLOGY%20INC")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(response.json()["vendors"][0]["metrics"]["award_count"], 2)
        invalid = self.client.get("/api/intelligence/market/vendors/compare/?vendors=ALPHA")
        self.assertEqual(invalid.status_code, 400)

    def test_agency_patterns_return_trends_concentration_and_active_opportunities(self):
        Opportunity.objects.create(source_id="v324-opp", title="Cloud modernization", agency="Department of the Army", active=True)
        payload = self.client.get("/api/intelligence/market/agencies/patterns/?name=Department%20of%20the%20Army").json()
        self.assertEqual(payload["metrics"]["award_count"], 2)
        self.assertEqual(payload["metrics"]["active_opportunities"], 1)
        self.assertTrue(payload["fiscal_years"])
        self.assertTrue(payload["top_vendors"])

    def test_market_map_and_vehicle_analysis_use_stored_awards(self):
        market = self.client.get("/api/intelligence/market/map/?type=naics&code=541512").json()
        self.assertEqual(market["code"], "541512")
        self.assertTrue(market["agencies"])
        self.assertTrue(market["vendors"])
        vehicle = self.client.get("/api/intelligence/market/vehicles/?q=ALPHA").json()
        self.assertEqual(vehicle["metrics"]["vehicle_count"], 1)
        self.assertEqual(vehicle["holders"][0]["recipient_name"], "ALPHA SYSTEMS LLC")

    def test_teaming_recommendations_exclude_current_company(self):
        payload = self.client.get("/api/intelligence/market/teaming/?naics=541512&psc=DA10&state=VA&vehicle=GSA%20MAS").json()
        names = [row["name"] for row in payload["results"]]
        self.assertNotIn(self.organization.name, names)
        self.assertEqual(names, ["Qualified Partner"])
        self.assertGreaterEqual(payload["results"][0]["score"], 90)

    def test_teaming_recommendations_exclude_blocked_companies(self):
        NetworkConnection.objects.create(requester=self.organization, recipient=self.other, status=NetworkConnection.Status.BLOCKED)
        payload = self.client.get("/api/intelligence/market/teaming/?naics=541512").json()
        self.assertEqual(payload["results"], [])

    def test_opportunity_incumbent_signal_uses_multiple_matching_factors(self):
        opportunity = Opportunity.objects.create(
            source_id="v324-incumbent", title="Cloud systems modernization support", agency="Department of the Army",
            naics_code="541512", psc_code="DA10", active=True, response_deadline=timezone.now() + timedelta(days=30),
        )
        payload = self.client.get(f"/api/intelligence/opportunities/{opportunity.source_id}/").json()
        incumbent = payload["data"]["incumbent"]
        self.assertEqual(incumbent["recipient_name"], "ALPHA SYSTEMS LLC")
        self.assertGreaterEqual(incumbent["confidence"], 70)
        self.assertEqual(incumbent["classification"], "forgegov_derived_incumbent_signal")

    def test_market_intelligence_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.get("/api/intelligence/market/map/?type=naics")
        self.assertEqual(response.status_code, 401)
