from django.db import migrations, models
import django.utils.timezone


PURSUIT_TO_PIPELINE_STAGE = {
    "triage": "reviewing",
    "qualify": "qualified",
    "bid_decision": "bid_decision",
    "capture": "capture",
    "proposal": "proposal",
    "submitted": "submitted",
    "awarded": "awarded",
    "lost": "lost",
    "no_bid": "no_bid",
    "archived": "archived",
}


def align_existing_pipeline_records(apps, schema_editor):
    Pursuit = apps.get_model("core", "Pursuit")
    PipelineItem = apps.get_model("core", "PipelineItem")
    for pursuit in Pursuit.objects.exclude(opportunity_id__isnull=True).iterator():
        pipeline = PipelineItem.objects.filter(
            organization_id=pursuit.organization_id,
            opportunity_id=pursuit.opportunity_id,
        ).first()
        if pipeline is None:
            continue
        if not pursuit.owner_id and pipeline.owner_id:
            pursuit.owner_id = pipeline.owner_id
            pursuit.save(update_fields=["owner_id"])
        values = {
            "stage": PURSUIT_TO_PIPELINE_STAGE.get(pursuit.stage, "capture"),
            "estimated_value": pursuit.estimated_value,
            "probability_of_win": pursuit.probability_of_win,
            "next_action": pursuit.next_action,
        }
        if pursuit.owner_id:
            values["owner_id"] = pursuit.owner_id
        PipelineItem.objects.filter(pk=pipeline.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("core", "0040_v326_forgeai_intelligence_platform")]

    operations = [
        migrations.AddField(
            model_name="savedsearch",
            name="last_evaluated_at",
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.RunPython(align_existing_pipeline_records, migrations.RunPython.noop),
    ]
