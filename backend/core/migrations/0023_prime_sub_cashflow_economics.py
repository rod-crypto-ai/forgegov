from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_price_to_win_intelligence"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricingplan",
            name="performance_months",
            field=models.DecimalField(decimal_places=2, default=12, max_digits=7),
        ),
        migrations.AddField(
            model_name="pricingplan",
            name="payment_lag_days",
            field=models.PositiveIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="pricingplan",
            name="mobilization_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20),
        ),
        migrations.AddField(
            model_name="pricingplan",
            name="available_working_capital",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20),
        ),
        migrations.CreateModel(
            name="PricingSubcontractor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=500)),
                ("quoted_cost", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("prime_markup_percent", models.DecimalField(decimal_places=3, default=0, max_digits=7)),
                ("management_burden", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("insurance_cost", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("contingency", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("deposit_percent", models.DecimalField(decimal_places=3, default=0, max_digits=7)),
                ("payment_terms_days", models.PositiveIntegerField(default=30)),
                ("monthly_burn", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("source", models.CharField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subcontractors", to="core.pricingplan")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddIndex(
            model_name="pricingsubcontractor",
            index=models.Index(fields=["plan", "name"], name="pricesub_plan_name_idx"),
        ),
    ]
