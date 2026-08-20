from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0002_rename_platform_ad_created_4cd240_idx_platform_ad_created_e2eecc_idx_and_more")]
    operations = [
        migrations.AlterField(
            model_name="platformadmingrant",
            name="role",
            field=models.CharField(choices=[("creator", "ForgeGov Creator / Platform Owner"), ("super_admin", "Platform Super Admin"), ("support_admin", "Platform Support Admin")], max_length=32),
        ),
    ]
