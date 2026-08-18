from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0027_data_integrity_connector_resilience")]

    operations = [
        migrations.AddField(
            model_name="organizationsecuritypolicy",
            name="require_mfa_for_exports",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organizationsecuritypolicy",
            name="require_mfa_for_project_room_admin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectroompartner",
            name="can_export",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectroompartner",
            name="can_view_sensitive_documents",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectroompartner",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectroompartner",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectroominvitation",
            name="can_export",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectroominvitation",
            name="can_view_sensitive_documents",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectroominvitation",
            name="partner_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="projectroomfile",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("internal", "Owner Company Only"),
                    ("shared", "All Project Room Participants"),
                    ("pricing", "Pricing Authorized Participants"),
                    ("sensitive", "Sensitive Document Authorized Participants"),
                ],
                default="shared",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="projectroompartner",
            index=models.Index(fields=["project_room", "revoked_at", "expires_at"], name="core_prpartner_access_idx"),
        ),
    ]
