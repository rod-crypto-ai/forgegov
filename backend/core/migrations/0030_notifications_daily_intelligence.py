from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0029_beta_feedback"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="intelligencealert",
            name="event_key",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="intelligencealert",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("new_opportunity", "New Opportunity"),
                    ("deadline", "Upcoming Deadline"),
                    ("amendment", "Amendment Posted"),
                    ("deadline_changed", "Response Deadline Changed"),
                    ("cancelled", "Opportunity Cancelled"),
                    ("document", "New Attachment"),
                    ("set_aside_changed", "Set-Aside Changed"),
                    ("status_changed", "Status Changed"),
                    ("pipeline", "Pipeline Update"),
                    ("project_room", "Project Room Update"),
                    ("award", "Award Intelligence"),
                    ("forecast", "Forecast Update"),
                ],
                default="new_opportunity",
                max_length=40,
            ),
        ),
        migrations.AddConstraint(
            model_name="intelligencealert",
            constraint=models.UniqueConstraint(
                fields=("organization", "event_key"),
                condition=~models.Q(event_key=""),
                name="unique_intelligence_alert_event_key",
            ),
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("in_app_enabled", models.BooleanField(default=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("immediate_critical", models.BooleanField(default=True)),
                ("daily_digest", models.BooleanField(default=True)),
                ("weekly_digest", models.BooleanField(default=False)),
                ("opportunity_alerts", models.BooleanField(default=True)),
                ("opportunity_changes", models.BooleanField(default=True)),
                ("deadlines", models.BooleanField(default=True)),
                ("pipeline", models.BooleanField(default=True)),
                ("project_room", models.BooleanField(default=True)),
                ("security", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to="core.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forgegov_notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="notificationpreference",
            constraint=models.UniqueConstraint(fields=("organization", "user"), name="unique_notification_preference_per_workspace"),
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(default="email", max_length=20)),
                ("category", models.CharField(blank=True, max_length=60)),
                ("recipient", models.EmailField(blank=True, max_length=254)),
                ("subject", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], default="sent", max_length=20)),
                ("error_message", models.CharField(blank=True, max_length=1000)),
                ("related_object_type", models.CharField(blank=True, max_length=80)),
                ("related_object_id", models.CharField(blank=True, max_length=120)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_deliveries", to="core.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forgegov_notification_deliveries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(fields=["organization", "status", "-created_at"], name="notif_delivery_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(fields=["user", "-created_at"], name="notif_delivery_user_idx"),
        ),
    ]
