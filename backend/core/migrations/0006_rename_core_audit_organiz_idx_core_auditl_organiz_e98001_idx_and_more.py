from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0005_fix_pending_invitation_constraint")]

    operations = [
        migrations.RenameIndex(
            model_name="auditlog",
            new_name="core_auditl_organiz_e98001_idx",
            old_name="core_audit_organiz_idx",
        ),
        migrations.RenameIndex(
            model_name="auditlog",
            new_name="core_auditl_action_d9fb24_idx",
            old_name="core_audit_action_idx",
        ),
    ]
