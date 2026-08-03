from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('core','0014_invitation_lifecycle_company_hub'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='projectroom',name='archived_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='projectroom',name='deleted_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='pipelineitem',name='project_room',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='pipeline_items',to='core.projectroom')),
        migrations.CreateModel(name='OrganizationJoinRequest',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('email_domain',models.CharField(max_length=255)),
            ('requested_role',models.CharField(choices=[('owner','Owner'),('admin','Administrator'),('capture','Capture Manager'),('bd','Business Development'),('proposal','Proposal Writer'),('viewer','Read Only')],default='viewer',max_length=20)),
            ('status',models.CharField(choices=[('pending','Pending'),('approved','Approved'),('declined','Declined'),('cancelled','Cancelled')],default='pending',max_length=20)),
            ('organization',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='join_requests',to='core.organization')),
            ('reviewed_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='reviewed_organization_join_requests',to=settings.AUTH_USER_MODEL)),
            ('reviewed_at',models.DateTimeField(blank=True,null=True)),
            ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='organization_join_requests',to=settings.AUTH_USER_MODEL)),
        ],options={'ordering':['-created_at']}),
        migrations.AddConstraint(model_name='organizationjoinrequest',constraint=models.UniqueConstraint(condition=models.Q(status='pending'),fields=('organization','user'),name='unique_pending_org_join_request')),
    ]
