from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('core','0013_project_room_members_pipeline_controls'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='membership',name='department',field=models.CharField(blank=True,max_length=120)),
        migrations.AddField(model_name='membership',name='active',field=models.BooleanField(default=True)),
        migrations.AddField(model_name='invitation',name='job_title',field=models.CharField(blank=True,max_length=120)),
        migrations.AddField(model_name='invitation',name='department',field=models.CharField(blank=True,max_length=120)),
        migrations.AddField(model_name='invitation',name='resend_count',field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name='invitation',name='last_sent_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='invitation',name='responded_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='invitation',name='accepted_by',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='accepted_forgegov_invitations',to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name='invitation',name='status',field=models.CharField(choices=[('pending','Pending'),('accepted','Accepted'),('declined','Declined'),('cancelled','Cancelled'),('revoked','Revoked'),('expired','Expired')],default='pending',max_length=20)),
        migrations.AddField(model_name='projectroominvitation',name='expires_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='projectroominvitation',name='last_sent_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='projectroominvitation',name='resend_count',field=models.PositiveSmallIntegerField(default=0)),
        migrations.AlterField(model_name='projectroominvitation',name='status',field=models.CharField(choices=[('pending','Pending'),('accepted','Accepted'),('declined','Declined'),('cancelled','Cancelled'),('expired','Expired')],default='pending',max_length=20)),
    ]
