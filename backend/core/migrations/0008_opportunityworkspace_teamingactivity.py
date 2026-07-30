from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("core", "0007_intelligencealert")]

    operations = [
        migrations.CreateModel(
            name="OpportunityWorkspace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("notes", models.TextField(blank=True)),
                ("capture_summary", models.TextField(blank=True)),
                ("risks", models.JSONField(blank=True, default=list)),
                ("compliance_items", models.JSONField(blank=True, default=list)),
                ("decision", models.CharField(default="undecided", max_length=20)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspaces", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="opportunity_workspaces", to="core.organization")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="opportunityworkspace",
            constraint=models.UniqueConstraint(fields=("organization", "opportunity"), name="unique_opportunity_workspace_per_org"),
        ),
        migrations.CreateModel(
            name="TeamingActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity_type", models.CharField(choices=[("note", "Note"), ("email", "Email"), ("call", "Call"), ("meeting", "Meeting"), ("follow_up", "Follow-up")], default="note", max_length=20)),
                ("subject", models.CharField(max_length=255)),
                ("details", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("follow_up_at", models.DateTimeField(blank=True, null=True)),
                ("completed", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teaming_activities", to="core.organization")),
                ("teaming_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="core.teamingrequest")),
            ],
            options={"ordering": ["-occurred_at", "-created_at"]},
        ),
    ]
