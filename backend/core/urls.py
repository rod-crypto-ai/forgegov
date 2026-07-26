from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .auth_views import (
    audit_logs,
    csrf_token,
    invitations,
    login,
    logout,
    me,
    refresh,
    register,
    team_member_detail,
    team_members,
)
from .views import (
    AgencyViewSet,
    AwardViewSet,
    CategoryViewSet,
    ContactGroupViewSet,
    ContactViewSet,
    DataSyncRunViewSet,
    FileRecordViewSet,
    OpportunityViewSet,
    OrganizationViewSet,
    ParticipantViewSet,
    PipelineItemViewSet,
    PursuitViewSet,
    SavedSearchViewSet,
    TaskViewSet,
    TeamingRequestViewSet,
    VendorViewSet,
    dashboard_summary,
    health,
    integration_status,
    live_sam_search,
    live_grants_search,
    live_grants_detail,
    live_usaspending_awards,
    add_opportunity_to_pipeline,
    ai_chat,
    pipeline_to_pursuit,
    create_saved_search,
    create_workspace_task,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("opportunities", OpportunityViewSet, basename="opportunity")
router.register("pipeline", PipelineItemViewSet, basename="pipeline-item")
router.register("pursuits", PursuitViewSet, basename="pursuit")
router.register("tasks", TaskViewSet, basename="task")
router.register("saved-searches", SavedSearchViewSet, basename="saved-search")
router.register("sync-runs", DataSyncRunViewSet, basename="sync-run")
router.register("agencies", AgencyViewSet, basename="agency")
router.register("vendors", VendorViewSet, basename="vendor")
router.register("awards", AwardViewSet, basename="award")
router.register("contacts", ContactViewSet, basename="contact")
router.register("contact-groups", ContactGroupViewSet, basename="contact-group")
router.register("teaming-requests", TeamingRequestViewSet, basename="teaming-request")
router.register("files", FileRecordViewSet, basename="file")
router.register("participants", ParticipantViewSet, basename="participant")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("auth/csrf/", csrf_token),
    path("auth/register/", register),
    path("auth/login/", login),
    path("auth/refresh/", refresh),
    path("auth/logout/", logout),
    path("auth/me/", me),
    path("team/members/", team_members),
    path("team/members/<int:membership_id>/", team_member_detail),
    path("team/invitations/", invitations),
    path("audit-logs/", audit_logs),
    path("health/", health),
    path("dashboard/summary/", dashboard_summary),
    path("integrations/status/", integration_status),
    path("ai/chat/", ai_chat),
    path("live/sam/opportunities/", live_sam_search),
    path("live/grants/opportunities/", live_grants_search),
    path("live/grants/opportunities/<str:opportunity_id>/", live_grants_detail),
    path("live/usaspending/awards/", live_usaspending_awards),
    path("workflow/opportunity-to-pipeline/", add_opportunity_to_pipeline),
    path("workflow/pipeline/<int:pipeline_id>/create-pursuit/", pipeline_to_pursuit),
    path("workflow/saved-searches/", create_saved_search),
    path("workflow/tasks/", create_workspace_task),
    path("", include(router.urls)),
]
