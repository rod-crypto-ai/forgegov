from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0016_network_connection_lifecycle")]
    operations = [
        migrations.AddField(model_name="award", name="parent_award_number", field=models.CharField(blank=True, db_index=True, max_length=160)),
        migrations.AddField(model_name="award", name="awarding_office", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="award", name="funding_office", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="award", name="recipient_cage", field=models.CharField(blank=True, max_length=16)),
        migrations.AddField(model_name="award", name="set_aside_code", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="award", name="jurisdiction_level", field=models.CharField(default="federal", max_length=24)),
        migrations.AddField(model_name="award", name="jurisdiction_code", field=models.CharField(blank=True, max_length=24)),
        migrations.AddField(model_name="award", name="source_updated_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name="ConnectorSource", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("key", models.SlugField(max_length=120, unique=True)), ("name", models.CharField(max_length=255)),
            ("scope", models.CharField(choices=[("federal","Federal"),("state","State"),("local","Local"),("commercial","Commercial")], default="federal", max_length=24)),
            ("jurisdiction_code", models.CharField(blank=True, max_length=24)), ("jurisdiction_name", models.CharField(blank=True, max_length=120)),
            ("official_url", models.URLField(blank=True)), ("documentation_url", models.URLField(blank=True)),
            ("license_name", models.CharField(blank=True, max_length=160)), ("license_url", models.URLField(blank=True)),
            ("authentication", models.CharField(blank=True, max_length=160)), ("capabilities", models.JSONField(blank=True, default=list)),
            ("enabled", models.BooleanField(default=True)), ("last_status", models.CharField(default="not_checked", max_length=40)),
            ("last_checked_at", models.DateTimeField(blank=True, null=True)), ("last_sync_at", models.DateTimeField(blank=True, null=True)),
            ("record_count", models.PositiveBigIntegerField(default=0)), ("rate_limit", models.CharField(blank=True, max_length=120)),
            ("last_error", models.TextField(blank=True)),
        ], options={"ordering":["scope","jurisdiction_name","name"]}),
        migrations.CreateModel(name="AwardSyncRun", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("connector_key", models.CharField(db_index=True, max_length=120)),
            ("status", models.CharField(choices=[("pending","Pending"),("running","Running"),("succeeded","Succeeded"),("failed","Failed"),("partial","Partial")], default="pending", max_length=20)),
            ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
            ("start_date", models.DateField(blank=True, null=True)), ("end_date", models.DateField(blank=True, null=True)),
            ("cursor", models.JSONField(blank=True, default=dict)), ("pages_processed", models.PositiveIntegerField(default=0)),
            ("records_seen", models.PositiveIntegerField(default=0)), ("records_created", models.PositiveIntegerField(default=0)),
            ("records_updated", models.PositiveIntegerField(default=0)), ("errors", models.JSONField(blank=True, default=list)),
        ], options={"ordering":["-created_at"]}),
    ]
