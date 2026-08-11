from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_prime_sub_cashflow_economics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PortfolioSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pipeline_value", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("weighted_pipeline_value", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("modeled_revenue", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("projected_profit", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("backlog_value", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("recommended_working_capital", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("working_capital_gap", models.DecimalField(decimal_places=2, default=0, max_digits=22)),
                ("portfolio_margin_percent", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("opportunity_count", models.PositiveIntegerField(default=0)),
                ("risk_summary", models.JSONField(blank=True, default=dict)),
                ("agency_concentration", models.JSONField(blank=True, default=list)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portfolio_snapshots", to="core.organization")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_portfolio_snapshots", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="portfoliosnapshot",
            index=models.Index(fields=["organization", "-created_at"], name="portfolio_org_time_idx"),
        ),
    ]
