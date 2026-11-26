from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import AuthSession, Membership, Organization, UserSecurityProfile


@override_settings(AXES_ENABLED=False)
class SessionRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "IsolatedSessionRegressionPassphrase123"
        self.user = get_user_model().objects.create_user(
            username="session@example.test", email="session@example.test", password=self.password,
        )
        organization = Organization.objects.create(name="Session QA", slug="session-qa")
        Membership.objects.create(user=self.user, organization=organization, role=Membership.Role.OWNER)
        UserSecurityProfile.objects.create(
            user=self.user, lifecycle_status=UserSecurityProfile.LifecycleStatus.ACTIVE,
            email_verified_at=timezone.now(),
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/auth/csrf/").json()["csrfToken"]
        response = self.client.post(
            "/api/auth/login/", {"email": self.user.email, "password": self.password},
            format="json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, 200)

    def refresh(self, client=None, **headers):
        return (client or self.client).post(
            "/api/auth/refresh/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf, **headers,
        )

    def test_expired_access_cookie_does_not_block_valid_refresh(self):
        token = AccessToken(self.client.cookies[settings.AUTH_ACCESS_COOKIE_NAME].value)
        token.set_exp(from_time=timezone.now() - timedelta(hours=1), lifetime=timedelta(seconds=1))
        self.client.cookies[settings.AUTH_ACCESS_COOKIE_NAME] = str(token)
        response = self.refresh()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_late_stale_refresh_cannot_clear_rotated_session_cookies(self):
        stale = self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        self.client.cookies.pop(settings.AUTH_ACCESS_COOKIE_NAME, None)
        self.assertEqual(self.refresh().status_code, 200)
        other_tab = APIClient(enforce_csrf_checks=True)
        other_tab.cookies["csrftoken"] = self.client.cookies["csrftoken"].value
        other_tab.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = stale
        rejected = self.refresh(other_tab)
        self.assertEqual(rejected.status_code, 401)
        self.assertNotIn(settings.AUTH_ACCESS_COOKIE_NAME, rejected.cookies)
        self.assertNotIn(settings.AUTH_REFRESH_COOKIE_NAME, rejected.cookies)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_revoked_session_cannot_be_refreshed(self):
        AuthSession.objects.filter(user=self.user).update(revoked_at=timezone.now())
        self.client.cookies.pop(settings.AUTH_ACCESS_COOKIE_NAME, None)
        self.assertEqual(self.refresh().status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_refresh_still_requires_csrf(self):
        self.client.cookies.pop(settings.AUTH_ACCESS_COOKIE_NAME, None)
        rejected = self.client.post("/api/auth/refresh/", {}, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(self.refresh().status_code, 200)
