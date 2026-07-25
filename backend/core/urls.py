from django.urls import include, path
from rest_framework.routers import DefaultRouter

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
    pipeline_to_pursuit,
    create_saved_search,
    create_workspace_task,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet)
router.register("opportunities", OpportunityViewSet, basename="opportunity")
router.register("pipeline", PipelineItemViewSet)
router.register("pursuits", PursuitViewSet, basename="pursuit")
router.register("tasks", TaskViewSet)
router.register("saved-searches", SavedSearchViewSet)
router.register("sync-runs", DataSyncRunViewSet, basename="sync-run")
router.register("agencies", AgencyViewSet, basename="agency")
router.register("vendors", VendorViewSet, basename="vendor")
router.register("awards", AwardViewSet, basename="award")
router.register("contacts", ContactViewSet, basename="contact")
router.register("contact-groups", ContactGroupViewSet)
router.register("teaming-requests", TeamingRequestViewSet, basename="teaming-request")
router.register("files", FileRecordViewSet, basename="file")
router.register("participants", ParticipantViewSet, basename="participant")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("health/", health),
    path("dashboard/summary/", dashboard_summary),
    path("integrations/status/", integration_status),
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
