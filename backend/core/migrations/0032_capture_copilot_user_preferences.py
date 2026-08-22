from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0031_capture_competitive_positioning"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("theme", models.CharField(choices=[("system", "System"), ("light", "Light"), ("dark", "Dark")], default="system", max_length=20)),
                ("density", models.CharField(choices=[("comfortable", "Comfortable"), ("compact", "Compact")], default="comfortable", max_length=20)),
                ("reduce_motion", models.BooleanField(default=False)),
                ("sidebar_collapsed", models.BooleanField(default=False)),
                ("ai_response_style", models.CharField(choices=[("concise", "Concise"), ("balanced", "Balanced"), ("detailed", "Detailed")], default="balanced", max_length=20)),
                ("ai_live_web_enabled", models.BooleanField(default=True)),
                ("ai_workspace_grounding_enabled", models.BooleanField(default=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="forgegov_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["user_id"]},
        ),
        migrations.AlterField(
            model_name="opportunityanalysis",
            name="analysis_type",
            field=models.CharField(choices=[("executive_summary", "Executive Summary"), ("requirements", "Requirements"), ("risks", "Risk Assessment"), ("bid_no_bid", "Bid / No-Bid"), ("compliance_matrix", "Compliance Matrix"), ("amendment_comparison", "Amendment Comparison"), ("capture_copilot", "Capture Copilot")], max_length=40),
        ),
        migrations.AddField(
            model_name="opportunityanalysis",
            name="contains_financial",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="opportunityanalysis",
            name="uses_workspace_context",
            field=models.BooleanField(default=True),
        ),
    ]
