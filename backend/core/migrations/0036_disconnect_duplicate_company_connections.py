from django.db import migrations


def disconnect_duplicate_company_connections(apps, schema_editor):
    Connection = apps.get_model("core", "NetworkConnection")
    for row in Connection.objects.select_related("requester", "recipient").filter(status__in=["pending", "accepted"]).iterator():
        left, right = row.requester, row.recipient
        same_name = left.name.strip().casefold() == right.name.strip().casefold()
        same_uei = bool(left.uei and right.uei and left.uei.strip().casefold() == right.uei.strip().casefold())
        same_cage = bool(left.cage_code and right.cage_code and left.cage_code.strip().casefold() == right.cage_code.strip().casefold())
        if same_name or same_uei or same_cage:
            row.status = "disconnected"
            row.save(update_fields=["status", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0035_company_logo_branding")]
    operations = [migrations.RunPython(disconnect_duplicate_company_connections, migrations.RunPython.noop)]
