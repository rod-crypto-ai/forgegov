from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0036_disconnect_duplicate_company_connections"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="proposalreview", name="gate_decision_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="proposalreview", name="gate_decision_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decided_proposal_reviews", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="proposalfinding", name="confidence", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="proposalfinding", name="recommendation", field=models.TextField(blank=True)),
        migrations.AddField(model_name="proposalfinding", name="resolution_response", field=models.TextField(blank=True)),
        migrations.AddField(model_name="proposalfinding", name="resolved_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="proposalfinding", name="resolved_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_proposal_findings", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="proposalfinding", name="section", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="review_findings", to="core.proposalsection")),
        migrations.CreateModel(
            name="ProposalReviewRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("review_type", models.CharField(choices=[("compliance", "Compliance Review"), ("pink", "Pink Team"), ("red", "Red Team"), ("gold", "Gold Team"), ("evaluator", "Simulated Evaluator"), ("final", "Final Readiness Review")], max_length=24)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=20)),
                ("input_fingerprint", models.CharField(max_length=64)),
                ("solicitation_snapshot", models.JSONField(blank=True, default=dict)), ("proposal_snapshot", models.JSONField(blank=True, default=dict)),
                ("scorecard", models.JSONField(blank=True, default=list)), ("summary", models.TextField(blank=True)),
                ("provider", models.CharField(blank=True, max_length=80)), ("model", models.CharField(blank=True, max_length=120)), ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="initiated_proposal_review_runs", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_runs", to="core.proposalplan")),
                ("review", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="runs", to="core.proposalreview")),
            ], options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="proposalreviewrun", index=models.Index(fields=["plan", "status", "review_type"], name="proprev_plan_stat_idx")),
        migrations.AddConstraint(model_name="proposalreviewrun", constraint=models.UniqueConstraint(condition=models.Q(("status__in", ["queued", "running"])), fields=("plan", "review_type", "input_fingerprint"), name="uniq_active_prop_review")),
        migrations.AddField(model_name="proposalfinding", name="review_run", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="findings", to="core.proposalreviewrun")),
        migrations.CreateModel(
            name="ProposalFindingEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_label", models.CharField(blank=True, max_length=500)), ("locator", models.CharField(blank=True, max_length=500)), ("quotation", models.TextField(blank=True)),
                ("document_chunk", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proposal_finding_evidence", to="core.opportunitydocumentchunk")),
                ("finding", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_items", to="core.proposalfinding")),
                ("requirement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finding_evidence", to="core.proposalrequirement")),
                ("review_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="evidence_items", to="core.proposalreviewrun")),
                ("revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finding_evidence", to="core.proposalsectionrevision")),
                ("section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finding_evidence", to="core.proposalsection")),
            ], options={"ordering": ["id"]},
        ),
        migrations.AddIndex(model_name="proposalfindingevidence", index=models.Index(fields=["finding", "review_run"], name="propfe_find_run_idx")),
        migrations.CreateModel(
            name="ProposalFindingComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField()), ("resolution_event", models.BooleanField(default=False)),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proposal_finding_comments", to=settings.AUTH_USER_MODEL)),
                ("finding", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="core.proposalfinding")),
            ], options={"ordering": ["created_at", "id"]},
        ),
    ]
