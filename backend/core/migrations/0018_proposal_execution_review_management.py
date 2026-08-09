from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_award_ingestion_connector_sdk"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProposalPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("planning","Planning"),("in_progress","In Progress"),("review","Review"),("submission_ready","Submission Ready"),("submitted","Submitted")], default="planning", max_length=30)),
                ("submission_method", models.CharField(blank=True, max_length=500)),
                ("final_submission_verified", models.BooleanField(default=False)),
                ("amendment_baseline", models.JSONField(blank=True, default=dict)),
                ("amendment_checked_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_proposal_plans", to=settings.AUTH_USER_MODEL)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proposal_plans", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proposal_plans", to="core.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ProposalRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=160)),
                ("requirement", models.TextField()),
                ("source", models.CharField(blank=True, max_length=500)),
                ("source_kind", models.CharField(blank=True, max_length=80)),
                ("evidence", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("needs_review","Needs Review"),("open","Open"),("in_progress","In Progress"),("compliant","Compliant"),("not_applicable","Not Applicable")], default="needs_review", max_length=30)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_proposal_requirements", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="core.proposalplan")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ProposalReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("review_type", models.CharField(choices=[("pink","Pink Team"),("red","Red Team"),("gold","Gold Team"),("final","Final Submission Check")], max_length=20)),
                ("target_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("planned","Planned"),("in_progress","In Progress"),("passed","Passed"),("blocked","Blocked")], default="planned", max_length=30)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("summary", models.TextField(blank=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_proposal_reviews", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="core.proposalplan")),
            ],
            options={"ordering": ["target_at", "id"]},
        ),
        migrations.CreateModel(
            name="ProposalFinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("severity", models.CharField(choices=[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")], default="medium", max_length=20)),
                ("title", models.CharField(max_length=500)),
                ("detail", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("open","Open"),("resolved","Resolved"),("accepted","Accepted Risk")], default="open", max_length=20)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_proposal_findings", to=settings.AUTH_USER_MODEL)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_proposal_findings", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="findings", to="core.proposalplan")),
                ("requirement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="findings", to="core.proposalrequirement")),
                ("review", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="findings", to="core.proposalreview")),
            ],
            options={"ordering": ["status", "-created_at"]},
        ),
        migrations.AddConstraint(model_name="proposalplan", constraint=models.UniqueConstraint(fields=("organization","opportunity"), name="unique_proposal_plan_per_org_opportunity")),
        migrations.AddIndex(model_name="proposalplan", index=models.Index(fields=["organization","status"], name="core_propplan_org_status_idx")),
        migrations.AddConstraint(model_name="proposalrequirement", constraint=models.UniqueConstraint(fields=("plan","key"), name="unique_proposal_requirement_key")),
        migrations.AddIndex(model_name="proposalrequirement", index=models.Index(fields=["plan","status"], name="core_propreq_plan_status_idx")),
        migrations.AddConstraint(model_name="proposalreview", constraint=models.UniqueConstraint(fields=("plan","review_type"), name="unique_proposal_review_type")),
        migrations.AddIndex(model_name="proposalfinding", index=models.Index(fields=["plan","status","severity"], name="propfind_plan_stat_idx")),
    ]
