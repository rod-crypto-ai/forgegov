from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_invitation_auditlog")]

    operations = [
        migrations.RemoveConstraint(
            model_name="invitation",
            name="unique_pending_invitation_per_org_email",
        ),
        migrations.AddConstraint(
            model_name="invitation",
            constraint=models.UniqueConstraint(
                fields=("organization", "email"),
                condition=models.Q(status="pending"),
                name="unique_pending_invitation_per_org_email",
            ),
        ),
    ]
