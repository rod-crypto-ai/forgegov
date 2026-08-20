from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import BetaFeedback, Membership, Organization
from platform_admin.models import PlatformAdminGrant, PlatformSetting

User=get_user_model()


class V311BetaStabilizationTests(TestCase):
    def setUp(self):
        self.org=Organization.objects.create(name="Beta Test Co",slug="beta-test-co")
        self.user=User.objects.create_user(username="tester@example.com",email="tester@example.com",password="StrongPassphrase123!")
        Membership.objects.create(organization=self.org,user=self.user,role=Membership.Role.OWNER)

    @override_settings(REGISTRATION_MODE="private_beta")
    def test_runtime_registration_mode_can_open_test_registration(self):
        PlatformSetting.objects.create(key="registration_mode",value={"mode":"public"})
        response=APIClient().get("/api/auth/registration-config/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["mode"],"public")
        self.assertTrue(response.json()["public_registration"])

    def test_authenticated_user_can_submit_beta_feedback(self):
        client=APIClient(); client.force_authenticate(self.user)
        response=client.post("/api/beta-feedback/",{"category":"suggestion","message":"Add clearer pursuit handoff controls.","page_path":"/capture/pursuits"},format="json")
        self.assertEqual(response.status_code,201)
        row=BetaFeedback.objects.get()
        self.assertEqual(row.organization,self.org)
        self.assertEqual(row.user,self.user)

    def test_creator_role_has_platform_owner_access(self):
        creator=User.objects.create_user(username="creator@example.com",email="creator@example.com",password="StrongPassphrase123!")
        PlatformAdminGrant.objects.create(user=creator,role="creator",is_active=True,mfa_verified=True)
        client=APIClient(); client.force_authenticate(creator)
        me=client.get("/api/platform-admin/me/")
        control=client.get("/api/platform-admin/creator-control/")
        self.assertEqual(me.status_code,200)
        self.assertEqual(me.json()["role"],"creator")
        self.assertEqual(control.status_code,200)

    def test_non_creator_cannot_use_creator_control(self):
        admin=User.objects.create_user(username="admin@example.com",email="admin@example.com",password="StrongPassphrase123!")
        PlatformAdminGrant.objects.create(user=admin,role="super_admin",is_active=True,mfa_verified=True)
        client=APIClient(); client.force_authenticate(admin)
        self.assertEqual(client.get("/api/platform-admin/creator-control/").status_code,403)
