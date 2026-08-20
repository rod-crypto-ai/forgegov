from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_governance_permissions_enterprise_controls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="BetaFeedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(choices=[("issue","Issue"),("suggestion","Suggestion"),("ux","User Experience"),("data","Data / Connector"),("other","Other")], default="issue", max_length=20)),
                ("status", models.CharField(choices=[("new","New"),("reviewing","Reviewing"),("planned","Planned"),("fixed","Fixed"),("closed","Closed")], default="new", max_length=20)),
                ("page_path", models.CharField(blank=True, max_length=500)),
                ("message", models.TextField()),
                ("user_agent", models.TextField(blank=True)),
                ("request_id", models.CharField(blank=True, max_length=120)),
                ("admin_notes", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="beta_feedback", to="core.organization")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forgegov_beta_feedback_resolved", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forgegov_beta_feedback", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="betafeedback", index=models.Index(fields=["status", "-created_at"], name="beta_feedback_status_idx")),
        migrations.AddIndex(model_name="betafeedback", index=models.Index(fields=["organization", "-created_at"], name="beta_feedback_org_idx")),
    ]
