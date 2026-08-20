from django.urls import path
from . import views

urlpatterns = [
    path("me/", views.me),
    path("dashboard/", views.dashboard),
    path("feedback/<int:feedback_id>/action/", views.feedback_action),
    path("feedback/", views.feedback_queue),
    path("creator-control/", views.creator_control),
    path("organizations/", views.organizations),
    path("organizations/<int:organization_id>/action/", views.organization_action),
    path("users/", views.users),
    path("users/<int:user_id>/action/", views.user_action),
    path("beta/", views.beta_applications),
    path("beta/<int:application_id>/action/", views.beta_action),
    path("feature-flags/", views.feature_flags),
    path("platform-state/", views.platform_state),
    path("audit/", views.audit_events),
    path("system/", views.system_operations),
    path("data-integrity/", views.data_integrity),
    path("data-integrity/quarantine/<int:quarantine_id>/retry/", views.retry_quarantine),
]
