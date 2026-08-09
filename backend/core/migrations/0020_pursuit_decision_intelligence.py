from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_submission_control_closeout"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PursuitDecisionSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recommendation", models.CharField(max_length=40)),
                ("win_probability", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("confidence", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("evidence_coverage", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("estimated_value", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("expected_value", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("target_margin_percent", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("pursuit_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("subcontractor_share_percent", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("scorecard", models.JSONField(blank=True, default=dict)),
                ("evidence", models.JSONField(blank=True, default=list)),
                ("conditions", models.JSONField(blank=True, default=list)),
                ("rationale", models.JSONField(blank=True, default=list)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pursuit_decisions", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pursuit_decisions", to="core.organization")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_pursuit_decisions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="pursuitdecisionsnapshot", index=models.Index(fields=["organization", "opportunity", "-created_at"], name="pdec_org_opp_time_idx")),
    ]
