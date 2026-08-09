from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_proposal_execution_review_management"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProposalCloseout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("submitted","Submitted"),("evaluation","Evaluation"),("discussions","Discussions"),("fpr","Final Proposal Revision"),("awarded","Awarded"),("lost","Lost"),("cancelled","Cancelled")], default="submitted", max_length=30)),
                ("awardee", models.CharField(blank=True, max_length=500)),
                ("award_value", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("award_date", models.DateField(blank=True, null=True)),
                ("debrief_requested", models.BooleanField(default=False)),
                ("debrief_received", models.BooleanField(default=False)),
                ("win_loss_reason", models.TextField(blank=True)),
                ("customer_feedback", models.TextField(blank=True)),
                ("strengths", models.JSONField(blank=True, default=list)),
                ("weaknesses", models.JSONField(blank=True, default=list)),
                ("lessons_learned", models.JSONField(blank=True, default=list)),
                ("plan", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="closeout", to="core.proposalplan")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_proposal_closeouts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ProposalSubmissionSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("delivery_method", models.CharField(blank=True, max_length=500)),
                ("confirmation_reference", models.CharField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                ("opportunity_snapshot", models.JSONField(blank=True, default=dict)),
                ("requirement_snapshot", models.JSONField(blank=True, default=list)),
                ("review_snapshot", models.JSONField(blank=True, default=list)),
                ("finding_snapshot", models.JSONField(blank=True, default=list)),
                ("file_manifest", models.JSONField(blank=True, default=list)),
                ("amendment_snapshot", models.JSONField(blank=True, default=dict)),
                ("snapshot_hash", models.CharField(max_length=64)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submission_snapshots", to="core.proposalplan")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proposal_submission_snapshots", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-submitted_at","-id"]},
        ),
        migrations.AddConstraint(
            model_name="proposalsubmissionsnapshot",
            constraint=models.UniqueConstraint(fields=("plan","sequence"), name="unique_prop_submit_sequence"),
        ),
        migrations.AddIndex(
            model_name="proposalsubmissionsnapshot",
            index=models.Index(fields=["plan","-submitted_at"], name="propsub_plan_time_idx"),
        ),
    ]
