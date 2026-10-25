import hashlib
import hmac
import importlib
import json
import time
from datetime import timedelta
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .billing import (
    BillingConfigurationError,
    BillingProviderError,
    create_checkout_session,
    create_portal_session,
    process_stripe_webhook,
    verify_stripe_signature,
)
from .models import (
    AuditLog,
    BillingEvent,
    Membership,
    Organization,
    OrganizationSubscription,
    SubscriptionPlan,
)
from .subscriptions import (
    ensure_organization_subscription,
    increment_usage,
    subscription_summary,
)
from .tenant_security import membership_capabilities
from .tests import AuthenticatedApiTestCase

User = get_user_model()


class CommercialReadinessApiTests(AuthenticatedApiTestCase):
    def test_owner_receives_tenant_scoped_legacy_access_without_checkout_claim(self):
        other = Organization.objects.create(
            name="Other Workspace", slug="other-workspace"
        )
        other_subscription = ensure_organization_subscription(other)
        other_subscription.seat_quantity = 99
        other_subscription.save(update_fields=["seat_quantity", "updated_at"])

        response = self.client.get("/api/billing/summary/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["organization"]["id"], self.organization.id)
        self.assertEqual(
            body["subscription"]["status"], OrganizationSubscription.Status.LEGACY
        )
        self.assertFalse(body["subscription"]["permits_access"])
        self.assertNotEqual(body["subscription"]["seat_quantity"], 99)
        self.assertFalse(body["billing"]["checkout_enabled"])
        self.assertFalse(body["billing"]["portal_enabled"])

    def test_non_admin_cannot_read_workspace_billing(self):
        viewer = User.objects.create_user(
            username="viewer-billing@example.com",
            email="viewer-billing@example.com",
            password="StrongPass!234",
        )
        Membership.objects.create(
            user=viewer, organization=self.organization, role=Membership.Role.VIEWER
        )
        client = APIClient()
        client.force_authenticate(viewer)

        response = client.get("/api/billing/summary/")

        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_start_checkout_or_open_portal(self):
        viewer = User.objects.create_user(
            username="viewer-actions@example.com",
            email="viewer-actions@example.com",
            password="StrongPass!234",
        )
        Membership.objects.create(
            user=viewer, organization=self.organization, role=Membership.Role.VIEWER
        )
        client = APIClient()
        client.force_authenticate(viewer)

        self.assertEqual(
            client.post("/api/billing/checkout/", {}, format="json").status_code, 403
        )
        self.assertEqual(
            client.post("/api/billing/portal/", {}, format="json").status_code, 403
        )

    @override_settings(BILLING_PROVIDER="stripe", BILLING_CHECKOUT_ENABLED=False)
    def test_checkout_fails_closed_without_complete_configuration(self):
        response = self.client.post("/api/billing/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 409)

    @override_settings(
        BILLING_PROVIDER="stripe",
        BILLING_CHECKOUT_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_example",
        STRIPE_WEBHOOK_SECRET="whsec_example",
        STRIPE_PRICE_ID="price_professional_annual",
    )
    @patch("core.views.create_checkout_session")
    def test_owner_can_start_hosted_checkout_and_action_is_audited(self, checkout_mock):
        checkout_mock.return_value = {
            "id": "cs_api_test",
            "url": "https://checkout.stripe.com/c/pay/cs_api_test",
        }
        response = self.client.post("/api/billing/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["url"], "https://checkout.stripe.com/c/pay/cs_api_test"
        )
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization, action="billing.checkout_started"
            ).exists()
        )

    @override_settings(
        BILLING_PROVIDER="stripe",
        BILLING_CHECKOUT_ENABLED=False,
        BILLING_PORTAL_ENABLED=True,
    )
    def test_portal_cannot_be_reported_available_when_checkout_is_disabled(self):
        body = subscription_summary(self.organization)
        self.assertEqual(body["billing"]["provider"], "stripe")
        self.assertFalse(body["billing"]["checkout_enabled"])
        self.assertFalse(body["billing"]["portal_enabled"])

    @override_settings(
        BILLING_PROVIDER="stripe",
        BILLING_CHECKOUT_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_example",
        STRIPE_WEBHOOK_SECRET="whsec_example",
        STRIPE_PRICE_ID="price_professional_annual",
        STRIPE_TRIAL_PAYMENT_METHOD_MODE="unconfigured",
    )
    def test_checkout_fails_closed_until_trial_payment_policy_is_explicit(self):
        body = subscription_summary(self.organization)
        self.assertFalse(body["billing"]["checkout_enabled"])
        self.assertFalse(body["billing"]["trial_policy_configured"])
        self.assertEqual(body["offer"]["price_cents"], 200000)
        self.assertEqual(body["offer"]["trial_days"], 30)

    @override_settings(
        BILLING_PROVIDER="stripe",
        BILLING_CHECKOUT_ENABLED=False,
        BILLING_PORTAL_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_example",
    )
    def test_existing_customer_portal_remains_available_when_new_checkout_is_disabled(
        self,
    ):
        subscription = ensure_organization_subscription(self.organization)
        subscription.provider = OrganizationSubscription.Provider.STRIPE
        subscription.provider_customer_id = "cus_existing"
        subscription.save(
            update_fields=["provider", "provider_customer_id", "updated_at"]
        )
        body = subscription_summary(self.organization)
        self.assertFalse(body["billing"]["checkout_enabled"])
        self.assertTrue(body["billing"]["portal_enabled"])
        self.assertTrue(body["billing"]["portal_available"])


class SubscriptionDomainTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Subscription Org", slug="subscription-org"
        )

    def test_existing_workspace_subscription_is_non_destructive_and_idempotent(self):
        first = ensure_organization_subscription(self.organization)
        second = ensure_organization_subscription(self.organization)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.plan.code, "professional-annual")
        self.assertFalse(first.permits_access)

    def test_company_name_alone_cannot_grant_grandfathered_access(self):
        named_after_launch = Organization.objects.create(
            name="Howard Dynamics", slug="new-howard-dynamics"
        )

        subscription = ensure_organization_subscription(named_after_launch)

        self.assertFalse(subscription.grandfathered)
        self.assertEqual(subscription.status, OrganizationSubscription.Status.LEGACY)

    def test_one_time_migration_grandfathers_only_existing_named_workspaces(self):
        howard = Organization.objects.create(
            name="Howard Dynamics LLC", slug="howard-dynamics-existing"
        )
        strictly = Organization.objects.create(
            name="Strictly Hunter", slug="strictly-hunter-existing"
        )
        lookalike = Organization.objects.create(
            name="Howard Dynamics Partners", slug="howard-dynamics-partners"
        )
        migration = importlib.import_module(
            "core.migrations.0042_v330_commercial_subscription_foundation"
        )

        migration.preserve_existing_workspace_access(apps, None)

        for organization in (howard, strictly):
            subscription = OrganizationSubscription.objects.get(
                organization=organization
            )
            self.assertTrue(subscription.grandfathered)
            self.assertEqual(
                subscription.status, OrganizationSubscription.Status.GRANDFATHERED
            )
            self.assertEqual(
                subscription.provider, OrganizationSubscription.Provider.DISABLED
            )
            self.assertIsNotNone(subscription.grandfathered_at)
        self.assertFalse(
            OrganizationSubscription.objects.get(organization=lookalike).grandfathered
        )

    def test_database_rejects_payment_provider_state_for_grandfathered_access(self):
        subscription = ensure_organization_subscription(self.organization)
        subscription.grandfathered = True
        subscription.grandfathered_at = timezone.now()
        subscription.grandfathered_reason = "Founding workspace subscription exemption"
        subscription.status = OrganizationSubscription.Status.GRANDFATHERED
        subscription.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationSubscription.objects.filter(pk=subscription.pk).update(
                provider=OrganizationSubscription.Provider.STRIPE,
                provider_customer_id="cus_forbidden",
            )

    def test_expired_trial_is_calculated_without_mutating_provider_state(self):
        plan = SubscriptionPlan.objects.create(
            code="trial", name="Trial", trial_days=14
        )
        subscription = OrganizationSubscription.objects.create(
            organization=self.organization,
            plan=plan,
            status=OrganizationSubscription.Status.TRIALING,
            trial_ends_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(
            subscription.access_state, OrganizationSubscription.Status.EXPIRED
        )
        self.assertFalse(subscription.permits_access)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, OrganizationSubscription.Status.TRIALING)

    def test_past_due_access_requires_an_explicit_unexpired_grace_period(self):
        plan = SubscriptionPlan.objects.create(code="paid", name="Paid", entitlements={"platform": True})
        subscription = OrganizationSubscription.objects.create(
            organization=self.organization,
            plan=plan,
            status=OrganizationSubscription.Status.PAST_DUE,
            provider=OrganizationSubscription.Provider.MANUAL,
        )
        self.assertEqual(
            subscription.access_state, OrganizationSubscription.Status.EXPIRED
        )
        self.assertFalse(subscription.permits_access)
        subscription.grace_ends_at = timezone.now() + timedelta(days=3)
        self.assertEqual(
            subscription.access_state, OrganizationSubscription.Status.PAST_DUE
        )
        self.assertTrue(subscription.permits_access)

    def test_usage_is_counted_in_a_monthly_window_and_plan_limit_is_explainable(self):
        subscription = ensure_organization_subscription(self.organization)
        subscription.plan.limits = {"forgeai_runs": 2}
        subscription.plan.save(update_fields=["limits", "updated_at"])

        first = increment_usage(self.organization, "forgeai_runs")
        second = increment_usage(self.organization, "forgeai_runs", 2)

        self.assertEqual(first.quantity, 1)
        self.assertTrue(first.permitted)
        self.assertEqual(second.quantity, 3)
        self.assertFalse(second.permitted)
        self.assertEqual(second.limit, 2)
        self.assertLess(second.period_starts_at, second.period_ends_at)

    def test_billing_events_are_replay_safe_and_store_only_a_digest(self):
        BillingEvent.objects.create(
            provider="stripe",
            provider_event_id="evt_1",
            event_type="subscription.updated",
            payload_digest="a" * 64,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            BillingEvent.objects.create(
                provider="stripe",
                provider_event_id="evt_1",
                event_type="subscription.updated",
                payload_digest="b" * 64,
            )

    def test_billing_administration_capability_is_limited_to_owner_and_admin(self):
        for role in (Membership.Role.OWNER, Membership.Role.ADMIN):
            capability = membership_capabilities(
                type("MembershipRole", (), {"role": role})()
            )
            self.assertTrue(capability["billing_admin"])
        for role in (
            Membership.Role.CAPTURE,
            Membership.Role.BD,
            Membership.Role.PROPOSAL,
            Membership.Role.PRICING,
            Membership.Role.CONTRIBUTOR,
            Membership.Role.VIEWER,
        ):
            capability = membership_capabilities(
                type("MembershipRole", (), {"role": role})()
            )
            self.assertFalse(capability["billing_admin"])


@override_settings(
    BILLING_PROVIDER="stripe",
    BILLING_CHECKOUT_ENABLED=True,
    BILLING_PORTAL_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_example",
    STRIPE_WEBHOOK_SECRET="whsec_example",
    STRIPE_PRICE_ID="price_professional_annual",
    STRIPE_TRIAL_PAYMENT_METHOD_MODE="required",
    STRIPE_WEBHOOK_TOLERANCE_SECONDS=300,
    BILLING_GRACE_DAYS=7,
    FRONTEND_URL="https://app.example.test",
)
class StripeBillingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Stripe Org", slug="stripe-org"
        )
        self.user = User.objects.create_user(
            username="billing-owner@example.com",
            email="billing-owner@example.com",
            password="StrongPass!234",
        )
        Membership.objects.create(
            user=self.user, organization=self.organization, role=Membership.Role.OWNER
        )

    @staticmethod
    def _signed(
        payload: bytes, *, timestamp: int | None = None, secret: str = "whsec_example"
    ) -> str:
        timestamp = timestamp or int(time.time())
        digest = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={digest}"

    @patch("core.billing.requests.request")
    def test_checkout_uses_server_owned_price_and_hosted_stripe_url(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/c/pay/cs_test_1",
        }
        request_mock.return_value = response

        result = create_checkout_session(organization=self.organization, user=self.user)

        self.assertEqual(result["id"], "cs_test_1")
        request_data = dict(request_mock.call_args.kwargs["data"])
        self.assertEqual(
            request_data["line_items[0][price]"], "price_professional_annual"
        )
        self.assertEqual(request_data["subscription_data[trial_period_days]"], "30")
        self.assertEqual(
            request_data["metadata[organization_id]"], str(self.organization.id)
        )
        self.assertNotIn("price_data[unit_amount]", request_data)

    @patch("core.billing.requests.request")
    def test_grandfathered_workspace_cannot_enter_checkout_or_portal(
        self, request_mock
    ):
        subscription = ensure_organization_subscription(self.organization)
        subscription.grandfathered = True
        subscription.grandfathered_at = timezone.now()
        subscription.grandfathered_reason = "Founding workspace subscription exemption"
        subscription.status = OrganizationSubscription.Status.GRANDFATHERED
        subscription.save()

        summary = subscription_summary(self.organization)
        self.assertTrue(summary["subscription"]["grandfathered"])
        self.assertEqual(
            summary["subscription"]["access_state"],
            OrganizationSubscription.Status.GRANDFATHERED,
        )
        self.assertTrue(summary["subscription"]["permits_access"])
        self.assertFalse(summary["billing"]["checkout_available"])
        self.assertFalse(summary["billing"]["portal_available"])
        with self.assertRaises(BillingConfigurationError):
            create_checkout_session(organization=self.organization, user=self.user)
        with self.assertRaises(BillingConfigurationError):
            create_portal_session(organization=self.organization)
        request_mock.assert_not_called()

    def test_signed_provider_event_cannot_change_grandfathered_access(self):
        subscription = ensure_organization_subscription(self.organization)
        subscription.grandfathered = True
        subscription.grandfathered_at = timezone.now()
        subscription.grandfathered_reason = "Founding workspace subscription exemption"
        subscription.status = OrganizationSubscription.Status.GRANDFATHERED
        subscription.save()
        event = {
            "id": "evt_grandfathered_protected",
            "type": "customer.subscription.updated",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": "sub_unwanted",
                    "customer": "cus_unwanted",
                    "status": "canceled",
                    "metadata": {"organization_id": str(self.organization.id)},
                    "items": {
                        "data": [
                            {
                                "quantity": 1,
                                "price": {"id": "price_professional_annual"},
                            }
                        ]
                    },
                }
            },
        }
        payload = json.dumps(event).encode()

        process_stripe_webhook(payload, self._signed(payload))

        subscription.refresh_from_db()
        self.assertTrue(subscription.grandfathered)
        self.assertEqual(
            subscription.status, OrganizationSubscription.Status.GRANDFATHERED
        )
        self.assertEqual(subscription.provider_subscription_id, "")

    @patch("core.billing.requests.request")
    def test_checkout_does_not_grant_a_second_trial(self, request_mock):
        subscription = ensure_organization_subscription(self.organization)
        subscription.trial_consumed_at = timezone.now() - timedelta(days=60)
        subscription.status = OrganizationSubscription.Status.CANCELLED
        subscription.save(update_fields=["trial_consumed_at", "status", "updated_at"])
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": "cs_returning",
            "url": "https://checkout.stripe.com/c/pay/cs_returning",
        }
        request_mock.return_value = response

        create_checkout_session(organization=self.organization, user=self.user)

        request_data = dict(request_mock.call_args.kwargs["data"])
        self.assertNotIn("subscription_data[trial_period_days]", request_data)

    @override_settings(STRIPE_TRIAL_PAYMENT_METHOD_MODE="optional_cancel")
    @patch("core.billing.requests.request")
    def test_optional_payment_method_trial_has_explicit_end_behavior(
        self, request_mock
    ):
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": "cs_optional",
            "url": "https://checkout.stripe.com/c/pay/cs_optional",
        }
        request_mock.return_value = response

        create_checkout_session(organization=self.organization, user=self.user)

        request_data = dict(request_mock.call_args.kwargs["data"])
        self.assertEqual(request_data["payment_method_collection"], "if_required")
        self.assertEqual(
            request_data[
                "subscription_data[trial_settings][end_behavior][missing_payment_method]"
            ],
            "cancel",
        )

    @patch("core.billing.requests.request")
    def test_unapproved_hosted_redirect_is_rejected(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {
            "id": "cs_bad",
            "url": "https://attacker.example/checkout",
        }
        request_mock.return_value = response
        with self.assertRaises(BillingProviderError):
            create_checkout_session(organization=self.organization, user=self.user)

        subscription = ensure_organization_subscription(self.organization)
        subscription.provider = OrganizationSubscription.Provider.STRIPE
        subscription.provider_customer_id = "cus_portal"
        subscription.save(
            update_fields=["provider", "provider_customer_id", "updated_at"]
        )
        response.json.return_value = {
            "id": "bps_bad",
            "url": "https://attacker.example/portal",
        }
        with self.assertRaises(BillingProviderError):
            create_portal_session(organization=self.organization)

    def test_webhook_signature_rejects_invalid_and_stale_requests(self):
        payload = b'{"id":"evt_signature","type":"noop","data":{"object":{}}}'
        verify_stripe_signature(payload, self._signed(payload))
        with self.assertRaises(BillingProviderError):
            verify_stripe_signature(payload, self._signed(payload, secret="wrong"))
        with self.assertRaises(BillingProviderError):
            verify_stripe_signature(
                payload, self._signed(payload, timestamp=int(time.time()) - 301)
            )

    def test_signed_subscription_event_updates_only_mapped_tenant_and_is_idempotent(
        self,
    ):
        other = Organization.objects.create(name="Unrelated", slug="unrelated")
        other_subscription = ensure_organization_subscription(other)
        event = {
            "id": "evt_subscription_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "status": "active",
                    "metadata": {"organization_id": str(self.organization.id)},
                    "current_period_start": int(time.time()),
                    "current_period_end": int(time.time()) + 86400,
                    "items": {
                        "data": [
                            {
                                "quantity": 4,
                                "price": {"id": "price_professional_annual"},
                            }
                        ]
                    },
                }
            },
        }
        payload = json.dumps(event, separators=(",", ":")).encode()

        first = process_stripe_webhook(payload, self._signed(payload))
        second = process_stripe_webhook(payload, self._signed(payload))

        subscription = OrganizationSubscription.objects.get(
            organization=self.organization
        )
        other_subscription.refresh_from_db()
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(subscription.status, OrganizationSubscription.Status.ACTIVE)
        self.assertEqual(subscription.provider_subscription_id, "sub_123")
        self.assertEqual(subscription.seat_quantity, 4)
        self.assertIsNotNone(subscription.trial_consumed_at)
        self.assertEqual(
            other_subscription.status, OrganizationSubscription.Status.LEGACY
        )
        self.assertEqual(
            AuditLog.objects.filter(action="billing.subscription_synced").count(), 1
        )
        receipt = BillingEvent.objects.get(provider_event_id="evt_subscription_1")
        self.assertEqual(receipt.payload_digest, hashlib.sha256(payload).hexdigest())
        self.assertNotIn("cus_123", receipt.payload_digest)

    def test_event_id_reuse_with_changed_payload_is_rejected(self):
        event = {"id": "evt_reused", "type": "noop", "data": {"object": {}}}
        first_payload = json.dumps(event).encode()
        process_stripe_webhook(first_payload, self._signed(first_payload))
        event["data"]["object"] = {"customer": "cus_changed"}
        second_payload = json.dumps(event).encode()
        with self.assertRaises(BillingProviderError):
            process_stripe_webhook(second_payload, self._signed(second_payload))

    def test_payment_failure_creates_explicit_grace_period(self):
        subscription = ensure_organization_subscription(self.organization)
        subscription.provider = OrganizationSubscription.Provider.STRIPE
        subscription.provider_customer_id = "cus_failure"
        subscription.save(
            update_fields=["provider", "provider_customer_id", "updated_at"]
        )
        event = {
            "id": "evt_invoice_failed",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_failure"}},
        }
        payload = json.dumps(event).encode()

        process_stripe_webhook(payload, self._signed(payload))

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, OrganizationSubscription.Status.PAST_DUE)
        self.assertTrue(subscription.permits_access)
        self.assertGreater(subscription.grace_ends_at, timezone.now())

        paid_event = {
            "id": "evt_invoice_paid",
            "type": "invoice.paid",
            "data": {"object": {"customer": "cus_failure"}},
        }
        paid_payload = json.dumps(paid_event).encode()
        process_stripe_webhook(paid_payload, self._signed(paid_payload))
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, OrganizationSubscription.Status.ACTIVE)
        self.assertIsNone(subscription.grace_ends_at)

    def test_invoice_metadata_cannot_remap_an_unknown_customer_to_a_workspace(self):
        subscription = ensure_organization_subscription(self.organization)
        event = {
            "id": "evt_unknown_invoice",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_unknown",
                    "metadata": {"organization_id": str(self.organization.id)},
                }
            },
        }
        payload = json.dumps(event).encode()

        process_stripe_webhook(payload, self._signed(payload))

        subscription.refresh_from_db()
        receipt = BillingEvent.objects.get(provider_event_id="evt_unknown_invoice")
        self.assertEqual(subscription.status, OrganizationSubscription.Status.LEGACY)
        self.assertIsNone(receipt.organization_id)

    def test_stale_provider_event_cannot_overwrite_newer_subscription_state(self):
        subscription = ensure_organization_subscription(self.organization)
        current_state_time = timezone.now()
        subscription.provider = OrganizationSubscription.Provider.STRIPE
        subscription.provider_customer_id = "cus_ordering"
        subscription.status = OrganizationSubscription.Status.ACTIVE
        subscription.provider_state_updated_at = current_state_time
        subscription.save(
            update_fields=[
                "provider",
                "provider_customer_id",
                "status",
                "provider_state_updated_at",
                "updated_at",
            ]
        )
        event = {
            "id": "evt_stale_failure",
            "type": "invoice.payment_failed",
            "created": int((current_state_time - timedelta(hours=1)).timestamp()),
            "data": {"object": {"customer": "cus_ordering"}},
        }
        payload = json.dumps(event).encode()

        process_stripe_webhook(payload, self._signed(payload))

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, OrganizationSubscription.Status.ACTIVE)
        self.assertEqual(subscription.provider_state_updated_at, current_state_time)

    def test_paid_invoice_cannot_reactivate_cancelled_subscription(self):
        subscription = ensure_organization_subscription(self.organization)
        subscription.provider = OrganizationSubscription.Provider.STRIPE
        subscription.provider_customer_id = "cus_cancelled"
        subscription.status = OrganizationSubscription.Status.CANCELLED
        subscription.save(
            update_fields=["provider", "provider_customer_id", "status", "updated_at"]
        )
        event = {
            "id": "evt_paid_after_cancel",
            "type": "invoice.paid",
            "created": int(time.time()),
            "data": {"object": {"customer": "cus_cancelled"}},
        }
        payload = json.dumps(event).encode()

        process_stripe_webhook(payload, self._signed(payload))

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, OrganizationSubscription.Status.CANCELLED)

    def test_subscription_event_with_unrecognized_price_is_rejected(self):
        event = {
            "id": "evt_wrong_price",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_wrong",
                    "customer": "cus_wrong",
                    "status": "active",
                    "metadata": {"organization_id": str(self.organization.id)},
                    "items": {
                        "data": [{"quantity": 1, "price": {"id": "price_untrusted"}}]
                    },
                }
            },
        }
        payload = json.dumps(event).encode()
        with self.assertRaises(BillingProviderError):
            process_stripe_webhook(payload, self._signed(payload))
        self.assertFalse(
            OrganizationSubscription.objects.filter(
                organization=self.organization,
                status=OrganizationSubscription.Status.ACTIVE,
            ).exists()
        )

    def test_webhook_endpoint_accepts_valid_signature_without_authentication(self):
        event = {"id": "evt_endpoint", "type": "noop", "data": {"object": {}}}
        payload = json.dumps(event).encode()
        client = APIClient()
        response = client.post(
            "/api/billing/stripe/webhook/",
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=self._signed(payload),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["received"])
