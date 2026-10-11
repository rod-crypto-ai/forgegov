from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0037_proposal_review_automation")]

    operations = [
        migrations.AddIndex(model_name="award", index=models.Index(fields=["recipient_uei", "recipient_name"], name="award_uei_name_idx")),
        migrations.AddIndex(model_name="award", index=models.Index(fields=["awarding_agency", "-start_date"], name="award_agency_start_idx")),
        migrations.AddIndex(model_name="award", index=models.Index(fields=["naics_code", "awarding_agency"], name="award_naics_agency_idx")),
        migrations.AddIndex(model_name="award", index=models.Index(fields=["psc_code", "awarding_agency"], name="award_psc_agency_idx")),
        migrations.AddIndex(model_name="award", index=models.Index(fields=["parent_award_number", "end_date"], name="award_parent_end_idx")),
        migrations.AddIndex(model_name="award", index=models.Index(fields=["award_type", "end_date"], name="award_type_end_idx")),
        migrations.AddIndex(model_name="contact", index=models.Index(fields=["organization", "vendor_name"], name="contact_org_vendor_idx")),
        migrations.AddIndex(model_name="teamingrequest", index=models.Index(fields=["organization", "company_name"], name="teaming_org_company_idx")),
    ]
