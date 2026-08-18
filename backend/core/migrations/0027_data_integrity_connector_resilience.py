from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("core", "0026_mfa_sessions_passkeys")]

    operations = [
        migrations.AlterField(
            model_name="datasyncrun",
            name="status",
            field=models.CharField(choices=[("running", "Running"), ("success", "Success"), ("partial", "Partial"), ("failed", "Failed")], default="running", max_length=20),
        ),
        migrations.CreateModel(
            name="SourceRecordVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.CharField(db_index=True, max_length=80)),
                ("record_type", models.CharField(db_index=True, max_length=80)),
                ("source_id", models.CharField(db_index=True, max_length=255)),
                ("fingerprint", models.CharField(db_index=True, max_length=64)),
                ("source_modified_at", models.DateTimeField(blank=True, null=True)),
                ("observed_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("provenance", models.JSONField(blank=True, default=dict)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-observed_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SyncQuarantine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.CharField(db_index=True, max_length=80)),
                ("record_type", models.CharField(db_index=True, max_length=80)),
                ("source_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("payload_hash", models.CharField(db_index=True, max_length=64)),
                ("reason", models.CharField(max_length=120)),
                ("error_message", models.CharField(blank=True, max_length=1000)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_note", models.CharField(blank=True, max_length=1000)),
                ("award_sync_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quarantine_records", to="core.awardsyncrun")),
                ("data_sync_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quarantine_records", to="core.datasyncrun")),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="sourcerecordversion",
            constraint=models.UniqueConstraint(fields=("source", "record_type", "source_id", "fingerprint"), name="uniq_source_record_version_fingerprint"),
        ),
        migrations.AddIndex(
            model_name="sourcerecordversion",
            index=models.Index(fields=["source", "record_type", "source_id", "-observed_at"], name="srcver_source_record_idx"),
        ),
        migrations.AddConstraint(
            model_name="syncquarantine",
            constraint=models.UniqueConstraint(fields=("source", "record_type", "payload_hash"), name="uniq_quarantine_source_record_hash"),
        ),
        migrations.AddIndex(
            model_name="syncquarantine",
            index=models.Index(fields=["source", "resolved_at", "-updated_at"], name="quarantine_source_state_idx"),
        ),
    ]
