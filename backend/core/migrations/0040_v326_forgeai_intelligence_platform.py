# Generated for ForgeGov v3.2.6 — ForgeAI Intelligence Platform.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0039_v325_capture_operations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ForgeAIResearchRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workflow", models.CharField(choices=[("research", "Research"), ("opportunity", "Opportunity"), ("capture", "Capture"), ("proposal", "Proposal"), ("market", "Market")], default="research", max_length=30)),
                ("status", models.CharField(choices=[("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="running", max_length=20)),
                ("request_fingerprint", models.CharField(max_length=64)),
                ("provider", models.CharField(blank=True, max_length=80)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("provider_response_id", models.CharField(blank=True, max_length=255)),
                ("provider_request_id", models.CharField(blank=True, max_length=255)),
                ("source_manifest", models.JSONField(blank=True, default=list)),
                ("evidence_summary", models.JSONField(blank=True, default=dict)),
                ("token_usage", models.JSONField(blank=True, default=dict)),
                ("used_live_web", models.BooleanField(default=False)),
                ("used_workspace_context", models.BooleanField(default=True)),
                ("financial_context_permitted", models.BooleanField(default=False)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="research_runs", to="core.aiconversation")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forgeai_research_runs", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forgeai_research_runs", to="core.organization")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="forgeairesearchrun",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "running")), fields=("organization", "created_by", "request_fingerprint"), name="uniq_running_forgeai_request"),
        ),
        migrations.AddIndex(
            model_name="forgeairesearchrun",
            index=models.Index(fields=["organization", "status", "-created_at"], name="forgeai_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="forgeairesearchrun",
            index=models.Index(fields=["organization", "workflow", "-created_at"], name="forgeai_org_workflow_idx"),
        ),
    ]
