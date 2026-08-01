from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_opportunityworkspace_teamingactivity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="job_title",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.CreateModel(
            name="ProjectRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("planning", "Planning"), ("active", "Active"), ("submitted", "Submitted"), ("closed", "Closed")], default="planning", max_length=20)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_project_rooms", to=settings.AUTH_USER_MODEL)),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="project_rooms", to="core.opportunity")),
                ("owner_organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="owned_project_rooms", to="core.organization")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ProjectRoomPartner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("access_level", models.CharField(choices=[("partner", "Teaming Partner"), ("subcontractor", "Subcontractor"), ("consultant", "Consultant"), ("viewer", "Viewer")], default="partner", max_length=20)),
                ("can_upload", models.BooleanField(default=True)),
                ("can_comment", models.BooleanField(default=True)),
                ("can_view_pricing", models.BooleanField(default=False)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="project_room_partner_invites", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shared_project_rooms", to="core.organization")),
                ("project_room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="partners", to="core.projectroom")),
            ],
        ),
        migrations.CreateModel(
            name="AIConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(default="New conversation", max_length=255)),
                ("visibility", models.CharField(choices=[("internal", "Owner Company Only"), ("shared", "Project Room Participants")], default="internal", max_length=20)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forgegov_ai_conversations", to=settings.AUTH_USER_MODEL)),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_conversations", to="core.opportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_conversations", to="core.organization")),
                ("project_room", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ai_conversations", to="core.projectroom")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="AIMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System")], max_length=20)),
                ("content", models.TextField()),
                ("sources", models.JSONField(blank=True, default=list)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("provider", models.CharField(blank=True, max_length=80)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="core.aiconversation")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="projectroompartner",
            constraint=models.UniqueConstraint(fields=("project_room", "organization"), name="unique_project_room_partner"),
        ),
        migrations.AddIndex(model_name="projectroom", index=models.Index(fields=["owner_organization", "status", "-updated_at"], name="core_projec_owner_o_0a7332_idx")),
        migrations.AddIndex(model_name="projectroompartner", index=models.Index(fields=["organization", "project_room"], name="core_projec_organiz_5d07a0_idx")),
        migrations.AddIndex(model_name="aiconversation", index=models.Index(fields=["organization", "-updated_at"], name="core_aicon_organiz_50f0c8_idx")),
        migrations.AddIndex(model_name="aiconversation", index=models.Index(fields=["project_room", "visibility"], name="core_aicon_project_26cf8b_idx")),
    ]
