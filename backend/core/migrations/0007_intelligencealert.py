from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0006_rename_core_audit_organiz_idx_core_auditl_organiz_e98001_idx_and_more")]

    operations = [
        migrations.CreateModel(
            name="IntelligenceAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alert_type", models.CharField(choices=[("new_opportunity", "New Opportunity"), ("deadline", "Upcoming Deadline"), ("award", "Award Intelligence"), ("forecast", "Forecast Update")], default="new_opportunity", max_length=40)),
                ("title", models.CharField(max_length=500)),
                ("summary", models.TextField(blank=True)),
                ("source_id", models.CharField(blank=True, max_length=255)),
                ("source_url", models.URLField(blank=True)),
                ("matched_filters", models.JSONField(blank=True, default=dict)),
                ("read", models.BooleanField(default=False)),
                ("dismissed", models.BooleanField(default=False)),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alerts", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="intelligence_alerts", to="core.organization")),
                ("saved_search", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alerts", to="core.savedsearch")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="intelligencealert",
            constraint=models.UniqueConstraint(fields=("organization", "saved_search", "source_id", "alert_type"), name="unique_saved_search_intelligence_alert"),
        ),
        migrations.AddIndex(
            model_name="intelligencealert",
            index=models.Index(fields=["organization", "read", "-created_at"], name="core_intell_organiz_3309e7_idx"),
        ),
        migrations.AddIndex(
            model_name="intelligencealert",
            index=models.Index(fields=["source_id"], name="core_intell_source__cba733_idx"),
        ),
    ]
