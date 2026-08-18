from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Membership, Organization, OrganizationSecurityPolicy, ProjectRoom, ProjectRoomFile, ProjectRoomMember, ProjectRoomPartner,
)
from .tenant_security import membership_capabilities, project_room_access, role_capability_matrix


class GovernanceV309Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_org = Organization.objects.create(name="Owner Co", slug="owner-co")
        self.partner_org = Organization.objects.create(name="Partner Co", slug="partner-co")
        self.owner_user = User.objects.create_user(username="owner@example.com", email="owner@example.com", password="StrongPass!234")
        self.partner_user = User.objects.create_user(username="partner@example.com", email="partner@example.com", password="StrongPass!234")
        self.owner_membership = Membership.objects.create(organization=self.owner_org, user=self.owner_user, role=Membership.Role.OWNER)
        self.partner_membership = Membership.objects.create(organization=self.partner_org, user=self.partner_user, role=Membership.Role.ADMIN)
        self.room = ProjectRoom.objects.create(owner_organization=self.owner_org, name="Enterprise Room", created_by=self.owner_user)
        ProjectRoomMember.objects.create(project_room=self.room, membership=self.owner_membership, role=ProjectRoomMember.Role.MANAGER)
        ProjectRoomMember.objects.create(project_room=self.room, membership=self.partner_membership, role=ProjectRoomMember.Role.MANAGER)
        self.partner = ProjectRoomPartner.objects.create(
            project_room=self.room, organization=self.partner_org, can_upload=True, can_comment=True, expires_at=timezone.now()+timedelta(days=30)
        )
        self.owner_client = APIClient(); self.owner_client.force_authenticate(self.owner_user)
        self.partner_client = APIClient(); self.partner_client.force_authenticate(self.partner_user)

    def test_role_matrix_matches_runtime_capabilities(self):
        matrix = role_capability_matrix()
        self.assertTrue(matrix[Membership.Role.OWNER]["export_data"])
        self.assertTrue(matrix[Membership.Role.PRICING]["financial_read"])
        self.assertFalse(matrix[Membership.Role.VIEWER]["sensitive_documents"])
        self.assertEqual(matrix[Membership.Role.OWNER], membership_capabilities(self.owner_membership))

    def test_expired_partner_grant_blocks_room_access(self):
        self.partner.expires_at = timezone.now()-timedelta(minutes=1)
        self.partner.save(update_fields=["expires_at", "updated_at"])
        response = self.partner_client.get(f"/api/project-rooms/{self.room.id}/files/")
        self.assertEqual(response.status_code, 404)

    def test_partner_file_visibility_requires_explicit_grants(self):
        ProjectRoomFile.objects.create(project_room=self.room, name="shared.pdf", url="https://example.com/shared.pdf", visibility="shared", uploaded_by=self.owner_user)
        ProjectRoomFile.objects.create(project_room=self.room, name="pricing.xlsx", url="https://example.com/pricing.xlsx", visibility="pricing", uploaded_by=self.owner_user)
        ProjectRoomFile.objects.create(project_room=self.room, name="sensitive.pdf", url="https://example.com/sensitive.pdf", visibility="sensitive", uploaded_by=self.owner_user)
        response = self.partner_client.get(f"/api/project-rooms/{self.room.id}/files/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["name"] for row in response.json()], ["shared.pdf"])
        self.partner.can_view_pricing = True
        self.partner.can_view_sensitive_documents = True
        self.partner.save(update_fields=["can_view_pricing", "can_view_sensitive_documents", "updated_at"])
        response = self.partner_client.get(f"/api/project-rooms/{self.room.id}/files/")
        self.assertEqual({row["name"] for row in response.json()}, {"shared.pdf", "pricing.xlsx", "sensitive.pdf"})

    def test_partner_export_requires_explicit_permission(self):
        denied = self.partner_client.get(f"/api/project-rooms/{self.room.id}/export/")
        self.assertEqual(denied.status_code, 403)
        self.partner.can_export = True
        self.partner.save(update_fields=["can_export", "updated_at"])
        allowed = self.partner_client.get(f"/api/project-rooms/{self.room.id}/export/")
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["effective_access"]["can_export"])


    def test_partner_room_detail_hides_other_partner_and_owner_pipeline_metadata(self):
        other_org = Organization.objects.create(name="Other Partner", slug="other-partner")
        ProjectRoomPartner.objects.create(project_room=self.room, organization=other_org, expires_at=timezone.now()+timedelta(days=30))
        response = self.partner_client.get(f"/api/project-rooms/{self.room.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["organization"] for row in response.json()["partners"]], [self.partner_org.id])
        self.assertEqual(response.json()["linked_pipeline_items"], [])

    def test_project_room_admin_policy_can_require_recent_authentication(self):
        OrganizationSecurityPolicy.objects.create(organization=self.owner_org, require_mfa_for_project_room_admin=True)
        response = self.owner_client.patch(
            f"/api/project-rooms/{self.room.id}/access/",
            {"kind": "partner", "organization": self.partner_org.id, "can_export": True},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_export_policy_can_require_recent_authentication(self):
        OrganizationSecurityPolicy.objects.create(organization=self.owner_org, require_mfa_for_exports=True)
        response = self.owner_client.get(f"/api/project-rooms/{self.room.id}/export/")
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_room_id_is_not_disclosed(self):
        outsider_org = Organization.objects.create(name="Outsider", slug="outsider")
        outsider = get_user_model().objects.create_user(username="out@example.com", email="out@example.com", password="StrongPass!234")
        Membership.objects.create(organization=outsider_org, user=outsider, role=Membership.Role.OWNER)
        client = APIClient(); client.force_authenticate(outsider)
        response = client.get(f"/api/project-rooms/{self.room.id}/files/")
        self.assertEqual(response.status_code, 404)
