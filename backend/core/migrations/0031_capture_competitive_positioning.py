from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0030_notifications_daily_intelligence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitivePositionSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("qualification_score", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("recommendation", models.CharField(max_length=40)),
                ("agency_profile", models.JSONField(blank=True, default=dict)),
                ("incumbent", models.JSONField(blank=True, default=dict)),
                ("competitors", models.JSONField(blank=True, default=list)),
                ("win_themes", models.JSONField(blank=True, default=list)),
                ("capture_gaps", models.JSONField(blank=True, default=list)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="competitive_position_snapshots", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="competitive_position_snapshots", to="core.organization")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_competitive_position_snapshots", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="competitivepositionsnapshot",
            index=models.Index(fields=["organization", "opportunity", "-created_at"], name="cpos_org_opp_time_idx"),
        ),
    ]
