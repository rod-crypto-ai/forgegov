from django.contrib import admin

from .models import DataSyncRun, Membership, Opportunity, Organization, PipelineItem, SavedSearch, Task


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "uei", "cage_code", "created_at")
    search_fields = ("name", "uei", "cage_code")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("title", "solicitation_number", "agency", "notice_type", "naics_code", "response_deadline", "active")
    list_filter = ("source", "notice_type", "active", "set_aside_code")
    search_fields = ("title", "solicitation_number", "agency", "subagency", "office", "naics_code", "psc_code")
    readonly_fields = ("raw_data", "created_at", "updated_at")


@admin.register(DataSyncRun)
class DataSyncRunAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "started_at", "finished_at", "records_received", "records_created", "records_updated")
    list_filter = ("source", "status")
    readonly_fields = ("started_at", "finished_at", "request_metadata", "created_at", "updated_at")


admin.site.register(Membership)
admin.site.register(PipelineItem)
admin.site.register(Task)
admin.site.register(SavedSearch)
