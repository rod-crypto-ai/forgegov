from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import Membership, Organization, OrganizationSubscription
from .subscriptions import ensure_organization_subscription


class SubscriptionEnforcementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='paywall@example.invalid', password='Password-For-Tests-234!')
        self.org = Organization.objects.create(name='Unpaid', slug='unpaid')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.sub = ensure_organization_subscription(self.org)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_unpaid_reads_and_writes_blocked_but_recovery_available(self):
        for path in ('/api/dashboard/summary/', '/api/ai/chat/', '/api/opportunities/'):
            for method in ('get', 'post'):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 403, (path, method, response.content))
                self.assertEqual(response.json()['code'], 'subscription_required')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.assertFalse(self.client.get('/api/auth/me/').json()['subscription']['permits_access'])
        self.assertEqual(self.client.get('/api/billing/summary/').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/workspaces/').status_code, 200)

    def test_cookie_and_session_cannot_bypass_gate(self):
        self.client.credentials()
        from django.conf import settings
        self.client.cookies[settings.AUTH_ACCESS_COOKIE_NAME] = str(AccessToken.for_user(self.user))
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)
        self.client.cookies.clear()
        self.client.force_login(self.user, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)

    def test_paid_period_expiry_is_enforced_without_waiting_for_webhook(self):
        self.sub.status = 'active'
        self.sub.provider = 'manual'
        self.sub.current_period_ends_at = timezone.now() + timedelta(days=2)
        self.sub.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 200)
        self.sub.current_period_ends_at = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)

    def test_status_label_or_company_rename_cannot_grant_free_access(self):
        self.sub.status = 'grandfathered'
        self.sub.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)
        self.org.name = 'Howard Dynamics'
        self.org.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)

    def test_explicit_grandfathered_flag_retains_access(self):
        self.sub.status = 'grandfathered'
        self.sub.grandfathered = True
        self.sub.grandfathered_at = timezone.now()
        self.sub.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 200)

    def test_workspace_selection_does_not_leak_paid_entitlement(self):
        paid = Organization.objects.create(name='Paid', slug='paid')
        Membership.objects.create(user=self.user, organization=paid, role='viewer')
        sub = ensure_organization_subscription(paid)
        sub.status = 'active'
        sub.provider = 'manual'
        sub.current_period_ends_at = timezone.now() + timedelta(days=2)
        sub.save()
        self.assertEqual(self.client.get('/api/dashboard/summary/', HTTP_X_FORGEGOV_ORGANIZATION=str(paid.id)).status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard/summary/', HTTP_X_FORGEGOV_ORGANIZATION=str(self.org.id)).status_code, 403)
