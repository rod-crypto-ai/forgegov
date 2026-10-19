from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Organization,
    OrganizationSubscription,
    SubscriptionPlan,
    SubscriptionUsageCounter,
)

LEGACY_PLAN_CODE = "legacy-full-access"
PROFESSIONAL_ANNUAL_PLAN_CODE = "professional-annual"


def legacy_plan() -> SubscriptionPlan:
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code=LEGACY_PLAN_CODE,
        defaults={
            "name": "Early Access",
            "description": "Protected access for workspaces created before automated billing is enabled.",
            "billing_interval": SubscriptionPlan.BillingInterval.MANUAL,
            "entitlements": {"platform": True},
            "limits": {},
            "active": True,
            "publicly_available": False,
        },
    )
    return plan


def professional_annual_plan() -> SubscriptionPlan:
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code=PROFESSIONAL_ANNUAL_PLAN_CODE,
        defaults={
            "name": "ForgeGov Professional",
            "description": "Annual government-contracting intelligence, capture, collaboration, proposal, and ForgeAI workspace access.",
            "currency": "USD",
            "price_cents": 200000,
            "billing_interval": SubscriptionPlan.BillingInterval.YEAR,
            "trial_days": 30,
            "entitlements": {"platform": True},
            "limits": {},
            "active": True,
            "publicly_available": True,
            "display_order": 10,
        },
    )
    return plan


def ensure_organization_subscription(
    organization: Organization,
) -> OrganizationSubscription:
    subscription, _ = OrganizationSubscription.objects.get_or_create(
        organization=organization,
        defaults={
            "plan": legacy_plan(),
            "status": OrganizationSubscription.Status.LEGACY,
            "provider": OrganizationSubscription.Provider.DISABLED,
            "seat_quantity": max(
                1, organization.memberships.filter(active=True).count()
            ),
        },
    )
    return subscription


def billing_configuration() -> dict[str, object]:
    provider = settings.BILLING_PROVIDER
    stripe_api_ready = bool(
        provider == OrganizationSubscription.Provider.STRIPE
        and settings.STRIPE_SECRET_KEY
    )
    stripe_ready = bool(
        stripe_api_ready and settings.STRIPE_WEBHOOK_SECRET and settings.STRIPE_PRICE_ID
    )
    trial_policy_ready = settings.STRIPE_TRIAL_PAYMENT_METHOD_MODE != "unconfigured"
    checkout_enabled = bool(
        settings.BILLING_CHECKOUT_ENABLED and stripe_ready and trial_policy_ready
    )
    return {
        "provider": provider,
        "checkout_enabled": checkout_enabled,
        "portal_enabled": bool(settings.BILLING_PORTAL_ENABLED and stripe_api_ready),
        "stripe_configured": stripe_ready,
        "trial_policy_configured": trial_policy_ready,
        "detail": (
            "Automated billing is configured."
            if checkout_enabled
            else "Automated billing is not fully configured. Existing workspace access is preserved."
        ),
    }


def subscription_summary(organization: Organization) -> dict[str, object]:
    subscription = ensure_organization_subscription(organization)
    plan = subscription.plan
    offer = professional_annual_plan()
    usage = SubscriptionUsageCounter.objects.filter(
        organization=organization,
        period_ends_at__gt=timezone.now(),
    ).order_by("metric", "-period_starts_at")
    latest_by_metric = {}
    for row in usage:
        latest_by_metric.setdefault(row.metric, row)
    configuration = billing_configuration()
    configuration["checkout_available"] = bool(
        configuration["checkout_enabled"]
        and not subscription.grandfathered
        and subscription.status
        in {
            OrganizationSubscription.Status.LEGACY,
            OrganizationSubscription.Status.CANCELLED,
            OrganizationSubscription.Status.EXPIRED,
        }
    )
    configuration["portal_available"] = bool(
        configuration["portal_enabled"]
        and not subscription.grandfathered
        and subscription.provider_customer_id
    )
    return {
        "organization": {"id": organization.id, "name": organization.name},
        "subscription": {
            "status": subscription.status,
            "access_state": subscription.access_state,
            "permits_access": subscription.permits_access,
            "provider": subscription.provider,
            "grandfathered": subscription.grandfathered,
            "grandfathered_at": subscription.grandfathered_at,
            "grandfathered_reason": subscription.grandfathered_reason,
            "seat_quantity": subscription.seat_quantity,
            "trial_available": (
                not subscription.grandfathered
                and not bool(subscription.trial_consumed_at)
            ),
            "trial_ends_at": subscription.trial_ends_at,
            "current_period_starts_at": subscription.current_period_starts_at,
            "current_period_ends_at": subscription.current_period_ends_at,
            "grace_ends_at": subscription.grace_ends_at,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        },
        "plan": {
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "currency": plan.currency,
            "price_cents": plan.price_cents,
            "billing_interval": plan.billing_interval,
            "entitlements": plan.entitlements,
            "limits": plan.limits,
        },
        "offer": {
            "code": offer.code,
            "name": offer.name,
            "description": offer.description,
            "currency": offer.currency,
            "price_cents": offer.price_cents,
            "billing_interval": offer.billing_interval,
            "trial_days": offer.trial_days,
        },
        "usage": [
            {
                "metric": row.metric,
                "quantity": row.quantity,
                "limit": plan.limits.get(row.metric),
                "period_starts_at": row.period_starts_at,
                "period_ends_at": row.period_ends_at,
            }
            for row in latest_by_metric.values()
        ],
        "billing": configuration,
    }


@dataclass(frozen=True)
class UsageResult:
    metric: str
    quantity: int
    limit: int | None
    permitted: bool
    period_starts_at: object
    period_ends_at: object


def _monthly_window(now=None):
    now = now or timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@transaction.atomic
def increment_usage(
    organization: Organization, metric: str, quantity: int = 1, *, now=None
) -> UsageResult:
    if quantity <= 0:
        raise ValueError("Usage quantity must be greater than zero.")
    subscription = ensure_organization_subscription(organization)
    start, end = _monthly_window(now)
    row, _ = SubscriptionUsageCounter.objects.select_for_update().get_or_create(
        organization=organization,
        metric=metric,
        period_starts_at=start,
        period_ends_at=end,
        defaults={"quantity": 0},
    )
    row.quantity = F("quantity") + quantity
    row.save(update_fields=["quantity", "updated_at"])
    row.refresh_from_db(fields=["quantity", "updated_at"])
    raw_limit = subscription.plan.limits.get(metric)
    limit = int(raw_limit) if raw_limit not in (None, "") else None
    return UsageResult(
        metric=metric,
        quantity=row.quantity,
        limit=limit,
        permitted=limit is None or row.quantity <= limit,
        period_starts_at=start,
        period_ends_at=end,
    )


def start_trial(
    organization: Organization, plan: SubscriptionPlan, *, days: int | None = None
) -> OrganizationSubscription:
    existing = ensure_organization_subscription(organization)
    if existing.grandfathered:
        raise ValueError("Grandfathered workspaces do not require a trial.")
    trial_days = plan.trial_days if days is None else days
    if trial_days <= 0:
        raise ValueError("A trial must have a positive duration.")
    now = timezone.now()
    subscription, _ = OrganizationSubscription.objects.update_or_create(
        organization=organization,
        defaults={
            "plan": plan,
            "status": OrganizationSubscription.Status.TRIALING,
            "provider": OrganizationSubscription.Provider.DISABLED,
            "trial_ends_at": now + timedelta(days=trial_days),
            "trial_consumed_at": now,
            "current_period_starts_at": now,
            "current_period_ends_at": now + timedelta(days=trial_days),
            "cancel_at_period_end": False,
            "cancelled_at": None,
        },
    )
    return subscription
