import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone

GRANDFATHERED_ORGANIZATION_NAMES = {
    "howard dynamics",
    "howard dynamics llc",
    "strictly hunter",
    "strictly hunter llc",
}
GRANDFATHERED_ORGANIZATION_SLUGS = {"howard-dynamics", "strictly-hunter"}


def _normalized_organization_name(value):
    return " ".join(
        str(value or "").casefold().replace(",", "").replace(".", "").split()
    )


def preserve_existing_workspace_access(apps, schema_editor):
    Organization = apps.get_model("core", "Organization")
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    OrganizationSubscription = apps.get_model("core", "OrganizationSubscription")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="legacy-full-access",
        defaults={
            "name": "Early Access",
            "description": "Protected access for workspaces created before automated billing is enabled.",
            "currency": "USD",
            "price_cents": 0,
            "billing_interval": "manual",
            "trial_days": 0,
            "entitlements": {"platform": True},
            "limits": {},
            "active": True,
            "publicly_available": False,
            "display_order": 0,
        },
    )
    SubscriptionPlan.objects.get_or_create(
        code="professional-annual",
        defaults={
            "name": "ForgeGov Professional",
            "description": "Annual government-contracting intelligence, capture, collaboration, proposal, and ForgeAI workspace access.",
            "currency": "USD",
            "price_cents": 200000,
            "billing_interval": "year",
            "trial_days": 30,
            "entitlements": {"platform": True},
            "limits": {},
            "active": True,
            "publicly_available": True,
            "display_order": 10,
        },
    )
    for organization in Organization.objects.all().iterator():
        seat_quantity = max(1, organization.memberships.filter(active=True).count())
        grandfathered = (
            _normalized_organization_name(organization.name)
            in GRANDFATHERED_ORGANIZATION_NAMES
            or str(organization.slug or "").casefold()
            in GRANDFATHERED_ORGANIZATION_SLUGS
        )
        subscription, created = OrganizationSubscription.objects.get_or_create(
            organization=organization,
            defaults={
                "plan": plan,
                "status": "grandfathered" if grandfathered else "legacy",
                "provider": "disabled",
                "seat_quantity": seat_quantity,
                "grandfathered": grandfathered,
                "grandfathered_at": timezone.now() if grandfathered else None,
                "grandfathered_reason": (
                    "Founding workspace subscription exemption" if grandfathered else ""
                ),
            },
        )
        if grandfathered and not created:
            subscription.plan = plan
            subscription.status = "grandfathered"
            subscription.provider = "disabled"
            subscription.provider_customer_id = ""
            subscription.provider_subscription_id = ""
            subscription.grandfathered = True
            subscription.grandfathered_at = (
                subscription.grandfathered_at or timezone.now()
            )
            subscription.grandfathered_reason = (
                "Founding workspace subscription exemption"
            )
            subscription.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0041_saved_search_watermark_pipeline_alignment")]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("price_cents", models.PositiveIntegerField(default=0)),
                (
                    "billing_interval",
                    models.CharField(
                        choices=[
                            ("month", "Monthly"),
                            ("year", "Annual"),
                            ("manual", "Manually managed"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("trial_days", models.PositiveSmallIntegerField(default=0)),
                ("entitlements", models.JSONField(blank=True, default=dict)),
                ("limits", models.JSONField(blank=True, default=dict)),
                ("active", models.BooleanField(default=True)),
                ("publicly_available", models.BooleanField(default=False)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["display_order", "price_cents", "id"]},
        ),
        migrations.CreateModel(
            name="OrganizationSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("grandfathered", "Grandfathered access"),
                            ("legacy", "Legacy access"),
                            ("trialing", "Trialing"),
                            ("active", "Active"),
                            ("past_due", "Past due"),
                            ("paused", "Paused"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                        ],
                        default="legacy",
                        max_length=20,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("disabled", "Not configured"),
                            ("manual", "Manually managed"),
                            ("stripe", "Stripe"),
                        ],
                        default="disabled",
                        max_length=20,
                    ),
                ),
                (
                    "provider_customer_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "provider_subscription_id",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "provider_state_updated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("grandfathered", models.BooleanField(default=False)),
                ("grandfathered_at", models.DateTimeField(blank=True, null=True)),
                ("grandfathered_reason", models.CharField(blank=True, max_length=255)),
                (
                    "seat_quantity",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("trial_consumed_at", models.DateTimeField(blank=True, null=True)),
                ("trial_ends_at", models.DateTimeField(blank=True, null=True)),
                (
                    "current_period_starts_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("current_period_ends_at", models.DateTimeField(blank=True, null=True)),
                ("grace_ends_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("provider_metadata", models.JSONField(blank=True, default=dict)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="core.organization",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="core.subscriptionplan",
                    ),
                ),
            ],
            options={"ordering": ["organization_id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionUsageCounter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metric", models.SlugField(max_length=100)),
                ("period_starts_at", models.DateTimeField()),
                ("period_ends_at", models.DateTimeField()),
                ("quantity", models.PositiveBigIntegerField(default=0)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_usage",
                        to="core.organization",
                    ),
                ),
            ],
            options={"ordering": ["-period_starts_at", "metric"]},
        ),
        migrations.CreateModel(
            name="BillingEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("disabled", "Not configured"),
                            ("manual", "Manually managed"),
                            ("stripe", "Stripe"),
                        ],
                        max_length=20,
                    ),
                ),
                ("provider_event_id", models.CharField(max_length=255)),
                ("event_type", models.CharField(max_length=160)),
                ("payload_digest", models.CharField(max_length=64)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("processing_error", models.CharField(blank=True, max_length=1000)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="billing_events",
                        to="core.organization",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="organizationsubscription",
            constraint=models.UniqueConstraint(
                condition=~models.Q(provider_customer_id=""),
                fields=("provider", "provider_customer_id"),
                name="uniq_subscription_provider_customer",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationsubscription",
            constraint=models.UniqueConstraint(
                condition=~models.Q(provider_subscription_id=""),
                fields=("provider", "provider_subscription_id"),
                name="uniq_subscription_provider_record",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationsubscription",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("grandfathered", False),
                    models.Q(
                        ("grandfathered", True),
                        ("grandfathered_at__isnull", False),
                        ("provider", "disabled"),
                        ("provider_customer_id", ""),
                        ("provider_subscription_id", ""),
                        ("status", "grandfathered"),
                    ),
                    _connector="OR",
                ),
                name="grandfathered_subscription_is_provider_free",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptionusagecounter",
            constraint=models.UniqueConstraint(
                fields=("organization", "metric", "period_starts_at", "period_ends_at"),
                name="uniq_subscription_usage_window",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptionusagecounter",
            constraint=models.CheckConstraint(
                condition=models.Q(period_ends_at__gt=models.F("period_starts_at")),
                name="subscription_usage_valid_window",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionusagecounter",
            index=models.Index(
                fields=["organization", "metric", "-period_starts_at"],
                name="subusage_org_metric_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="billingevent",
            constraint=models.UniqueConstraint(
                fields=("provider", "provider_event_id"),
                name="uniq_billing_provider_event",
            ),
        ),
        migrations.AddIndex(
            model_name="billingevent",
            index=models.Index(
                fields=["provider", "event_type", "-created_at"],
                name="billing_provider_type_idx",
            ),
        ),
        migrations.RunPython(
            preserve_existing_workspace_access, migrations.RunPython.noop
        ),
    ]
