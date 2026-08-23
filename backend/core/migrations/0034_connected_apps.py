from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0033_proposal_automation_live_web"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectedApp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("microsoft", "Microsoft 365")], max_length=40)),
                ("status", models.CharField(choices=[("connected", "Connected"), ("error", "Error"), ("disconnected", "Disconnected")], default="connected", max_length=20)),
                ("external_account_id", models.CharField(blank=True, max_length=255)),
                ("account_email", models.EmailField(blank=True, max_length=254)),
                ("tenant_id", models.CharField(blank=True, max_length=255)),
                ("scopes", models.JSONField(blank=True, default=list)),
                ("access_token_encrypted", models.TextField(blank=True)),
                ("refresh_token_encrypted", models.TextField(blank=True)),
                ("token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_error", models.CharField(blank=True, max_length=1000)),
                ("connected_at", models.DateTimeField(blank=True, null=True)),
                ("disconnected_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="connected_apps", to="core.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forgegov_connected_apps", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["provider", "user_id"]},
        ),
        migrations.AddConstraint(
            model_name="connectedapp",
            constraint=models.UniqueConstraint(fields=("organization", "user", "provider"), name="uniq_connected_app_user_provider"),
        ),
        migrations.AddIndex(
            model_name="connectedapp",
            index=models.Index(fields=["organization", "provider", "status"], name="connapp_org_prov_idx"),
        ),
    ]
