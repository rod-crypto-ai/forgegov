from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0015_teaming_workspace_domain_join")]
    operations=[migrations.AlterField(model_name="networkconnection",name="status",field=models.CharField(choices=[("pending","Pending"),("accepted","Accepted"),("declined","Declined"),("blocked","Blocked"),("cancelled","Cancelled"),("disconnected","Disconnected")],default="pending",max_length=20))]
