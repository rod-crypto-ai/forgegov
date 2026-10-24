from django.contrib import admin
from .models import PublicInquiry


@admin.register(PublicInquiry)
class PublicInquiryAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "email", "purpose", "status", "created_at")
    list_filter = ("purpose", "status")
    search_fields = ("company", "name", "email", "reference")
    readonly_fields = ("reference", "created_at", "updated_at")

from .models import (
    Agency,
    Award,
    BillingEvent,
    Category,
    Contact,
    ContactGroup,
    DataSyncRun,
    FileRecord,
    IntelligenceAlert,
    Membership,
    Opportunity,
    Organization,
    OrganizationSubscription,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    SubscriptionPlan,
    SubscriptionUsageCounter,
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
    IntelligenceAlert,
    Participant,
    Category,
    SubscriptionPlan,
    SubscriptionUsageCounter,
    BillingEvent,
):
    admin.site.register(model)


@admin.register(OrganizationSubscription)
class OrganizationSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "status",
        "provider",
        "grandfathered",
        "updated_at",
    )
    list_filter = ("status", "provider", "grandfathered")
    search_fields = ("organization__name", "organization__slug")
    readonly_fields = (
        "grandfathered",
        "grandfathered_at",
        "grandfathered_reason",
    )
