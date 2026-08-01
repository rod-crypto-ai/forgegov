from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0009_project_rooms_ai_conversations"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="OpportunityDocument", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("file_name", models.CharField(max_length=500)), ("source_url", models.URLField(max_length=2000)), ("content_type", models.CharField(blank=True,max_length=150)), ("checksum", models.CharField(blank=True,max_length=64)),
            ("status", models.CharField(choices=[("pending","Pending"),("ready","Ready"),("failed","Failed")],default="pending",max_length=20)), ("page_count",models.PositiveIntegerField(default=0)), ("character_count",models.PositiveIntegerField(default=0)), ("error_message",models.CharField(blank=True,max_length=1000)), ("metadata",models.JSONField(blank=True,default=dict)),
            ("opportunity",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="ingested_documents",to="core.opportunity")), ("organization",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="opportunity_documents",to="core.organization")), ("project_room",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="documents",to="core.projectroom")),
        ], options={"ordering":["file_name"]}),
        migrations.CreateModel(name="OpportunityDocumentChunk", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("created_at",models.DateTimeField(auto_now_add=True)), ("updated_at",models.DateTimeField(auto_now=True)), ("ordinal",models.PositiveIntegerField()), ("page_number",models.PositiveIntegerField(blank=True,null=True)), ("section",models.CharField(blank=True,max_length=255)), ("text",models.TextField()), ("document",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="chunks",to="core.opportunitydocument")),
        ], options={"ordering":["document_id","ordinal"]}),
        migrations.CreateModel(name="OpportunityAnalysis", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("created_at",models.DateTimeField(auto_now_add=True)), ("updated_at",models.DateTimeField(auto_now=True)), ("analysis_type",models.CharField(choices=[("executive_summary","Executive Summary"),("requirements","Requirements"),("risks","Risk Assessment"),("bid_no_bid","Bid / No-Bid"),("compliance_matrix","Compliance Matrix"),("amendment_comparison","Amendment Comparison")],max_length=40)), ("content",models.TextField()), ("sources",models.JSONField(blank=True,default=list)), ("model",models.CharField(blank=True,max_length=120)), ("input_fingerprint",models.CharField(max_length=64)),
            ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="created_opportunity_analyses",to=settings.AUTH_USER_MODEL)), ("opportunity",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="analyses",to="core.opportunity")), ("organization",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="opportunity_analyses",to="core.organization")), ("project_room",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="analyses",to="core.projectroom")),
        ], options={"ordering":["-updated_at"]}),
        migrations.AddConstraint(model_name="opportunitydocument",constraint=models.UniqueConstraint(fields=("organization","opportunity","source_url"),name="unique_ingested_opportunity_document")),
        migrations.AddIndex(model_name="opportunitydocument",index=models.Index(fields=["organization","opportunity","status"],name="core_oppdoc_org_opp_status_idx")),
        migrations.AddConstraint(model_name="opportunitydocumentchunk",constraint=models.UniqueConstraint(fields=("document","ordinal"),name="unique_opportunity_document_chunk")),
        migrations.AddIndex(model_name="opportunitydocumentchunk",index=models.Index(fields=["document","page_number","ordinal"],name="core_oppchunk_doc_page_idx")),
        migrations.AddConstraint(model_name="opportunityanalysis",constraint=models.UniqueConstraint(fields=("organization","opportunity","project_room","analysis_type","input_fingerprint"),name="unique_cached_opportunity_analysis")),
        migrations.AddIndex(model_name="opportunityanalysis",index=models.Index(fields=["organization","opportunity","analysis_type"],name="core_oppanalysis_org_type_idx")),
    ]
