from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0012_forgegov_network"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="pipelineitem", name="follow_up_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="pipelineitem", name="priority", field=models.CharField(default="medium", max_length=20)),
        migrations.AddField(model_name="pipelineitem", name="assigned_team", field=models.CharField(blank=True, max_length=120)),
        migrations.CreateModel(
            name="ProjectRoomMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(choices=[("manager","Manager"),("contributor","Contributor"),("viewer","Viewer")], default="contributor", max_length=20)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="added_project_room_members", to=settings.AUTH_USER_MODEL)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_room_memberships", to="core.membership")),
                ("project_room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="core.projectroom")),
            ],
            options={"indexes":[models.Index(fields=["project_room","role"], name="core_prmember_room_role_idx")]},
        ),
        migrations.AddConstraint(model_name="projectroommember", constraint=models.UniqueConstraint(fields=("project_room","membership"), name="unique_project_room_member")),
    ]
