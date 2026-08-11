from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_pricing_engine"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceToWinSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("competitive_floor", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("target_price", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("protective_ceiling", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("confidence", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("evidence_count", models.PositiveIntegerField(default=0)),
                ("comparable_award_ids", models.JSONField(blank=True, default=list)),
                ("assumptions", models.JSONField(blank=True, default=list)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("model_inputs", models.JSONField(blank=True, default=dict)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_to_win_snapshots", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_to_win_snapshots", to="core.organization")),
                ("pricing_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="price_to_win_snapshots", to="core.pricingplan")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_price_to_win_snapshots", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="pricetowinsnapshot",
            index=models.Index(fields=["organization", "opportunity", "-created_at"], name="ptw_org_opp_time_idx"),
        ),
    ]
