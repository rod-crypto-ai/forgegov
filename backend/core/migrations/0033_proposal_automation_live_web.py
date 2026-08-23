from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0032_capture_copilot_user_preferences"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProposalVolume",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=120)),
                ("title", models.CharField(max_length=500)),
                ("instructions", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("planning", "Planning"), ("drafting", "Drafting"), ("review", "Review"), ("approved", "Approved")], default="planning", max_length=20)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("page_limit", models.PositiveIntegerField(blank=True, null=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_proposal_volumes", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="volumes", to="core.proposalplan")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="proposalvolume",
            constraint=models.UniqueConstraint(fields=("plan", "key"), name="uniq_proposal_volume_key"),
        ),
        migrations.AddIndex(
            model_name="proposalvolume",
            index=models.Index(fields=["plan", "status", "sort_order"], name="propvol_plan_stat_idx"),
        ),
        migrations.CreateModel(
            name="ProposalSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=120)),
                ("title", models.CharField(max_length=500)),
                ("section_type", models.CharField(choices=[("cover", "Cover / Executive"), ("technical", "Technical"), ("management", "Management / Staffing"), ("past_performance", "Past Performance"), ("pricing", "Pricing / Cost"), ("other", "Other")], default="other", max_length=30)),
                ("instructions", models.TextField(blank=True)),
                ("content", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("planning", "Planning"), ("drafting", "Drafting"), ("review", "Review"), ("approved", "Approved"), ("locked", "Locked")], default="planning", max_length=20)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("last_ai_provider", models.CharField(blank=True, max_length=80)),
                ("last_ai_model", models.CharField(blank=True, max_length=120)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_proposal_sections", to=settings.AUTH_USER_MODEL)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_proposal_sections", to=settings.AUTH_USER_MODEL)),
                ("volume", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sections", to="core.proposalvolume")),
            ],
            options={"ordering": ["volume__sort_order", "sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="proposalsection",
            constraint=models.UniqueConstraint(fields=("volume", "key"), name="uniq_proposal_section_key"),
        ),
        migrations.AddIndex(
            model_name="proposalsection",
            index=models.Index(fields=["volume", "status", "sort_order"], name="propsec_vol_stat_idx"),
        ),
        migrations.CreateModel(
            name="ProposalSectionRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("notes", models.CharField(blank=True, max_length=1000)),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="section_links", to="core.proposalrequirement")),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_links", to="core.proposalsection")),
            ],
        ),
        migrations.AddConstraint(
            model_name="proposalsectionrequirement",
            constraint=models.UniqueConstraint(fields=("section", "requirement"), name="uniq_prop_section_requirement"),
        ),
        migrations.AddIndex(
            model_name="proposalsectionrequirement",
            index=models.Index(fields=["section", "requirement"], name="propsec_req_idx"),
        ),
        migrations.CreateModel(
            name="ProposalSectionRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("content", models.TextField(blank=True)),
                ("change_summary", models.CharField(blank=True, max_length=1000)),
                ("source_snapshot", models.JSONField(blank=True, default=dict)),
                ("ai_generated", models.BooleanField(default=False)),
                ("provider", models.CharField(blank=True, max_length=80)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proposal_section_revisions", to=settings.AUTH_USER_MODEL)),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="core.proposalsection")),
            ],
            options={"ordering": ["-revision", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="proposalsectionrevision",
            constraint=models.UniqueConstraint(fields=("section", "revision"), name="uniq_prop_section_revision"),
        ),
        migrations.AddIndex(
            model_name="proposalsectionrevision",
            index=models.Index(fields=["section", "-revision"], name="propsec_rev_idx"),
        ),
        migrations.CreateModel(
            name="ProposalLibraryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=500)),
                ("category", models.CharField(default="general", max_length=80)),
                ("content", models.TextField()),
                ("tags", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("approved", "Approved"), ("retired", "Retired")], default="draft", max_length=20)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_proposal_library_entries", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_proposal_library_entries", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proposal_library_entries", to="core.organization")),
                ("source_section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_entries", to="core.proposalsection")),
            ],
            options={"ordering": ["category", "title"]},
        ),
        migrations.AddIndex(
            model_name="proposallibraryentry",
            index=models.Index(fields=["organization", "status", "category"], name="proplib_org_stat_idx"),
        ),
    ]
