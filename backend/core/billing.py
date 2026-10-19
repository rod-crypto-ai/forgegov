from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import AuditLog, BillingEvent, Organization, OrganizationSubscription
from .subscriptions import (
    billing_configuration,
    ensure_organization_subscription,
    professional_annual_plan,
)


class BillingConfigurationError(RuntimeError):
    pass


class BillingProviderError(RuntimeError):
    pass


def _validated_hosted_url(value: object, *, expected_host: str) -> str:
    url = str(value or "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise BillingProviderError(
            "Stripe did not return an approved hosted billing URL."
        )
    return url


def _stripe_request(
    method: str, path: str, *, data=None, idempotency_key: str | None = None
) -> dict[str, Any]:
    if not settings.STRIPE_SECRET_KEY:
        raise BillingConfigurationError("Stripe is not configured.")
    headers = {
        "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        response = requests.request(
            method,
            f"{settings.STRIPE_API_BASE_URL}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise BillingProviderError(
            "Stripe could not be reached. Try again shortly."
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise BillingProviderError("Stripe returned an invalid response.") from exc
    if response.status_code >= 400:
        detail = (
            (payload.get("error") or {}).get("message")
            if isinstance(payload, dict)
            else None
        ) or "Stripe rejected the request."
        raise BillingProviderError(str(detail)[:500])
    if not isinstance(payload, dict):
        raise BillingProviderError("Stripe returned an invalid response.")
    return payload


def create_checkout_session(*, organization: Organization, user) -> dict[str, str]:
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        raise BillingConfigurationError(
            "This workspace has permanent grandfathered access and does not require a subscription."
        )
    configuration = billing_configuration()
    if not configuration["checkout_enabled"]:
        raise BillingConfigurationError(
            "Stripe Checkout is not enabled for this ForgeGov deployment."
        )
    plan = professional_annual_plan()
    success_url = f"{settings.FRONTEND_URL.rstrip('/')}/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.FRONTEND_URL.rstrip('/')}/billing?checkout=cancelled"
    data: list[tuple[str, str]] = [
        ("mode", "subscription"),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("client_reference_id", str(organization.id)),
        ("line_items[0][price]", settings.STRIPE_PRICE_ID),
        ("line_items[0][quantity]", "1"),
        ("metadata[organization_id]", str(organization.id)),
        ("subscription_data[metadata][organization_id]", str(organization.id)),
        ("billing_address_collection", "required"),
    ]
    if not subscription.trial_consumed_at and plan.trial_days:
        data.append(("subscription_data[trial_period_days]", str(plan.trial_days)))
        if settings.STRIPE_TRIAL_PAYMENT_METHOD_MODE in {
            "optional_cancel",
            "optional_pause",
        }:
            end_behavior = (
                "cancel"
                if settings.STRIPE_TRIAL_PAYMENT_METHOD_MODE == "optional_cancel"
                else "pause"
            )
            data.extend(
                [
                    ("payment_method_collection", "if_required"),
                    (
                        "subscription_data[trial_settings][end_behavior][missing_payment_method]",
                        end_behavior,
                    ),
                ]
            )
    if subscription.provider_customer_id:
        data.append(("customer", subscription.provider_customer_id))
    else:
        data.append(("customer_email", user.email))
    payload = _stripe_request(
        "POST",
        "checkout/sessions",
        data=data,
        idempotency_key=f"forgegov-checkout-{organization.id}-{secrets.token_hex(12)}",
    )
    if not payload.get("id") or not payload.get("url"):
        raise BillingProviderError("Stripe did not return a hosted Checkout URL.")
    return {
        "id": str(payload["id"]),
        "url": _validated_hosted_url(
            payload["url"], expected_host="checkout.stripe.com"
        ),
    }


def create_portal_session(*, organization: Organization) -> dict[str, str]:
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        raise BillingConfigurationError(
            "This workspace has permanent grandfathered access and does not require billing management."
        )
    configuration = billing_configuration()
    if not configuration["portal_enabled"]:
        raise BillingConfigurationError(
            "The Stripe Customer Portal is not enabled for this ForgeGov deployment."
        )
    if not subscription.provider_customer_id:
        raise BillingConfigurationError(
            "This workspace does not have a Stripe customer record yet."
        )
    payload = _stripe_request(
        "POST",
        "billing_portal/sessions",
        data={
            "customer": subscription.provider_customer_id,
            "return_url": f"{settings.FRONTEND_URL.rstrip('/')}/billing",
        },
        idempotency_key=f"forgegov-portal-{organization.id}-{secrets.token_hex(12)}",
    )
    if not payload.get("id") or not payload.get("url"):
        raise BillingProviderError("Stripe did not return a Customer Portal URL.")
    return {
        "id": str(payload["id"]),
        "url": _validated_hosted_url(
            payload["url"], expected_host="billing.stripe.com"
        ),
    }


def verify_stripe_signature(
    payload: bytes, signature_header: str, *, now: int | None = None
) -> None:
    if settings.BILLING_PROVIDER != OrganizationSubscription.Provider.STRIPE:
        raise BillingConfigurationError(
            "Stripe webhooks are not enabled for this ForgeGov deployment."
        )
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingConfigurationError(
            "Stripe webhook verification is not configured."
        )
    values: dict[str, list[str]] = {}
    for part in signature_header.split(","):
        key, separator, value = part.strip().partition("=")
        if separator:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise BillingProviderError("Stripe signature header is invalid.") from exc
    current = int(time.time() if now is None else now)
    if abs(current - timestamp) > settings.STRIPE_WEBHOOK_TOLERANCE_SECONDS:
        raise BillingProviderError(
            "Stripe webhook timestamp is outside the allowed tolerance."
        )
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in values.get("v1", [])):
        raise BillingProviderError("Stripe webhook signature is invalid.")


def _as_datetime(value):
    try:
        return datetime.fromtimestamp(int(value), tz=UTC) if value else None
    except (TypeError, ValueError, OverflowError):
        return None


def _object_metadata(obj: dict[str, Any]) -> dict[str, Any]:
    metadata = obj.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _organization_for_stripe_object(obj: dict[str, Any]) -> Organization | None:
    subscription_id = (
        obj.get("subscription")
        if isinstance(obj.get("subscription"), str)
        else obj.get("id")
    )
    customer_id = obj.get("customer")
    match = OrganizationSubscription.objects.select_related("organization").filter(
        provider=OrganizationSubscription.Provider.STRIPE
    )
    if subscription_id:
        found = match.filter(provider_subscription_id=str(subscription_id)).first()
        if found:
            return found.organization
    if customer_id:
        found = match.filter(provider_customer_id=str(customer_id)).first()
        if found:
            return found.organization
    raw_id = _object_metadata(obj).get("organization_id") or obj.get(
        "client_reference_id"
    )
    if raw_id and str(raw_id).isdigit():
        return Organization.objects.filter(pk=int(raw_id)).first()
    return None


def _subscription_for_invoice(obj: dict[str, Any]) -> OrganizationSubscription | None:
    match = OrganizationSubscription.objects.select_related("organization").filter(
        provider=OrganizationSubscription.Provider.STRIPE,
    )
    subscription_id = obj.get("subscription")
    if isinstance(subscription_id, str) and subscription_id:
        found = match.filter(provider_subscription_id=subscription_id).first()
        if found:
            return found
    customer_id = obj.get("customer")
    if customer_id:
        return match.filter(provider_customer_id=str(customer_id)).first()
    return None


def _subscription_period(obj: dict[str, Any]):
    start = obj.get("current_period_start")
    end = obj.get("current_period_end")
    items = (
        ((obj.get("items") or {}).get("data") or [])
        if isinstance(obj.get("items"), dict)
        else []
    )
    if items and isinstance(items[0], dict):
        start = start or items[0].get("current_period_start")
        end = end or items[0].get("current_period_end")
    return _as_datetime(start), _as_datetime(end)


def _subscription_price_id(obj: dict[str, Any]) -> str:
    items = (
        ((obj.get("items") or {}).get("data") or [])
        if isinstance(obj.get("items"), dict)
        else []
    )
    if not items or not isinstance(items[0], dict):
        return ""
    price = items[0].get("price")
    if isinstance(price, dict):
        return str(price.get("id") or "")
    return str(price or "")


def _stripe_status(value: str) -> str:
    return {
        "trialing": OrganizationSubscription.Status.TRIALING,
        "active": OrganizationSubscription.Status.ACTIVE,
        "past_due": OrganizationSubscription.Status.PAST_DUE,
        "unpaid": OrganizationSubscription.Status.PAST_DUE,
        "paused": OrganizationSubscription.Status.PAUSED,
        "canceled": OrganizationSubscription.Status.CANCELLED,
        "incomplete": OrganizationSubscription.Status.PAUSED,
        "incomplete_expired": OrganizationSubscription.Status.EXPIRED,
    }.get(value, OrganizationSubscription.Status.PAUSED)


@transaction.atomic
def _apply_checkout_event(
    event_type: str, obj: dict[str, Any], organization: Organization
) -> OrganizationSubscription | None:
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        return None
    subscription.plan = professional_annual_plan()
    subscription.provider = OrganizationSubscription.Provider.STRIPE
    subscription.provider_customer_id = str(
        obj.get("customer") or subscription.provider_customer_id
    )
    subscription.provider_subscription_id = str(
        obj.get("subscription") or subscription.provider_subscription_id
    )
    subscription.save(
        update_fields=[
            "plan",
            "provider",
            "provider_customer_id",
            "provider_subscription_id",
            "updated_at",
        ]
    )
    return subscription


@transaction.atomic
def _apply_subscription_event(
    event_type: str,
    obj: dict[str, Any],
    organization: Organization,
    event_created_at: datetime,
) -> OrganizationSubscription | None:
    price_id = _subscription_price_id(obj)
    if price_id != settings.STRIPE_PRICE_ID:
        raise BillingProviderError(
            "Stripe subscription price does not match the configured ForgeGov plan."
        )
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        return None
    if (
        subscription.provider_state_updated_at
        and event_created_at < subscription.provider_state_updated_at
    ):
        return None
    period_start, period_end = _subscription_period(obj)
    mapped_status = (
        OrganizationSubscription.Status.CANCELLED
        if event_type == "customer.subscription.deleted"
        else _stripe_status(str(obj.get("status") or ""))
    )
    subscription.plan = professional_annual_plan()
    subscription.provider = OrganizationSubscription.Provider.STRIPE
    subscription.provider_customer_id = str(
        obj.get("customer") or subscription.provider_customer_id
    )
    subscription.provider_subscription_id = str(
        obj.get("id") or subscription.provider_subscription_id
    )
    subscription.provider_state_updated_at = event_created_at
    subscription.status = mapped_status
    items = (
        ((obj.get("items") or {}).get("data") or [])
        if isinstance(obj.get("items"), dict)
        else []
    )
    item_quantity = (
        items[0].get("quantity") if items and isinstance(items[0], dict) else None
    )
    subscription.seat_quantity = max(1, int(item_quantity or obj.get("quantity") or 1))
    subscription.trial_ends_at = _as_datetime(obj.get("trial_end"))
    subscription.trial_consumed_at = subscription.trial_consumed_at or timezone.now()
    subscription.current_period_starts_at = period_start
    subscription.current_period_ends_at = period_end
    subscription.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    subscription.cancelled_at = _as_datetime(obj.get("canceled_at"))
    subscription.grace_ends_at = (
        timezone.now() + timedelta(days=settings.BILLING_GRACE_DAYS)
        if mapped_status == OrganizationSubscription.Status.PAST_DUE
        else None
    )
    subscription.provider_metadata = {
        "livemode": bool(obj.get("livemode")),
        "collection_method": str(obj.get("collection_method") or "")[:40],
    }
    subscription.save()
    return subscription


@transaction.atomic
def _apply_invoice_failure(
    organization: Organization, event_created_at: datetime
) -> OrganizationSubscription | None:
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        return None
    if (
        subscription.provider_state_updated_at
        and event_created_at < subscription.provider_state_updated_at
    ):
        return None
    if subscription.status in {
        OrganizationSubscription.Status.CANCELLED,
        OrganizationSubscription.Status.EXPIRED,
        OrganizationSubscription.Status.PAUSED,
    }:
        return None
    subscription.status = OrganizationSubscription.Status.PAST_DUE
    subscription.provider_state_updated_at = event_created_at
    subscription.grace_ends_at = timezone.now() + timedelta(
        days=settings.BILLING_GRACE_DAYS
    )
    subscription.save(
        update_fields=[
            "status",
            "provider_state_updated_at",
            "grace_ends_at",
            "updated_at",
        ]
    )
    return subscription


@transaction.atomic
def _apply_invoice_success(
    organization: Organization, event_created_at: datetime
) -> OrganizationSubscription | None:
    subscription = ensure_organization_subscription(organization)
    if subscription.grandfathered:
        return None
    if (
        subscription.provider_state_updated_at
        and event_created_at < subscription.provider_state_updated_at
    ):
        return None
    if subscription.status != OrganizationSubscription.Status.PAST_DUE:
        return None
    subscription.status = OrganizationSubscription.Status.ACTIVE
    subscription.provider_state_updated_at = event_created_at
    subscription.grace_ends_at = None
    subscription.save(
        update_fields=[
            "status",
            "provider_state_updated_at",
            "grace_ends_at",
            "updated_at",
        ]
    )
    return subscription


def process_stripe_webhook(payload: bytes, signature_header: str) -> dict[str, Any]:
    verify_stripe_signature(payload, signature_header)
    try:
        event = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise BillingProviderError("Stripe webhook payload is invalid JSON.") from exc
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise BillingProviderError("Stripe webhook event is incomplete.")
    event_id = str(event["id"])
    event_type = str(event["type"])
    event_created_at = _as_datetime(event.get("created")) or timezone.now()
    digest = hashlib.sha256(payload).hexdigest()
    try:
        receipt, created = BillingEvent.objects.get_or_create(
            provider=OrganizationSubscription.Provider.STRIPE,
            provider_event_id=event_id,
            defaults={"event_type": event_type, "payload_digest": digest},
        )
    except IntegrityError:
        receipt = BillingEvent.objects.get(
            provider=OrganizationSubscription.Provider.STRIPE,
            provider_event_id=event_id,
        )
        created = False
    if not hmac.compare_digest(receipt.payload_digest, digest):
        raise BillingProviderError(
            "Stripe event ID was reused with a different payload."
        )
    if not created and receipt.processed_at:
        return {"received": True, "duplicate": True, "event_id": event_id}
    obj = (
        ((event.get("data") or {}).get("object"))
        if isinstance(event.get("data"), dict)
        else None
    ) or {}
    if not isinstance(obj, dict):
        raise BillingProviderError("Stripe webhook object is invalid.")
    invoice_event = event_type in {
        "invoice.paid",
        "invoice.payment_succeeded",
        "invoice.payment_failed",
    }
    invoice_subscription = _subscription_for_invoice(obj) if invoice_event else None
    organization = (
        invoice_subscription.organization
        if invoice_subscription
        else (None if invoice_event else _organization_for_stripe_object(obj))
    )
    try:
        subscription = None
        if organization and event_type == "checkout.session.completed":
            subscription = _apply_checkout_event(event_type, obj, organization)
        elif organization and event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            subscription = _apply_subscription_event(
                event_type, obj, organization, event_created_at
            )
        elif invoice_subscription and event_type == "invoice.payment_failed":
            subscription = _apply_invoice_failure(
                invoice_subscription.organization, event_created_at
            )
        elif invoice_subscription and event_type in {
            "invoice.paid",
            "invoice.payment_succeeded",
        }:
            subscription = _apply_invoice_success(
                invoice_subscription.organization, event_created_at
            )
        if organization:
            receipt.organization = organization
        receipt.processed_at = timezone.now()
        receipt.processing_error = ""
        receipt.save(
            update_fields=[
                "organization",
                "processed_at",
                "processing_error",
                "updated_at",
            ]
        )
        if subscription:
            AuditLog.objects.create(
                organization=organization,
                action="billing.subscription_synced",
                object_type="organization_subscription",
                object_id=str(subscription.id),
                metadata={
                    "provider": "stripe",
                    "event_type": event_type,
                    "provider_event_id": event_id,
                    "status": subscription.status,
                },
            )
        return {"received": True, "duplicate": False, "event_id": event_id}
    except Exception as exc:
        receipt.processing_error = f"{type(exc).__name__}: event processing failed"[
            :1000
        ]
        receipt.save(update_fields=["processing_error", "updated_at"])
        raise
