from django.contrib import admin
from .models import (
    PlatformAdminGrant, OrganizationControlState, UserControlState,
    BetaApplication, FeatureFlag, PlatformSetting, PlatformAuditEvent,
)

admin.site.register(PlatformAdminGrant)
admin.site.register(OrganizationControlState)
admin.site.register(UserControlState)
admin.site.register(BetaApplication)
admin.site.register(FeatureFlag)
admin.site.register(PlatformSetting)
admin.site.register(PlatformAuditEvent)
