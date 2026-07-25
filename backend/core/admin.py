from django.contrib import admin

from .models import (
    Agency,
    Award,
    Category,
    Contact,
    ContactGroup,
    DataSyncRun,
    FileRecord,
    Membership,
    Opportunity,
    Organization,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    Task,
    TeamingRequest,
    Vendor,
)

admin.site.site_header = "ForgeGov Administration"
admin.site.site_title = "ForgeGov Admin"
admin.site.index_title = "Government contracting data and capture operations"

for model in (
    Organization,
    Membership,
    Opportunity,
    PipelineItem,
    Pursuit,
    Task,
    SavedSearch,
    DataSyncRun,
    Agency,
    Vendor,
    Award,
    Contact,
    ContactGroup,
    TeamingRequest,
    FileRecord,
    Participant,
    Category,
):
    admin.site.register(model)
