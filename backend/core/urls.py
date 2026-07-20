from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DataSyncRunViewSet,
    OpportunityViewSet,
    OrganizationViewSet,
    PipelineItemViewSet,
    SavedSearchViewSet,
    TaskViewSet,
    dashboard_summary,
    health,
    integration_status,
    live_sam_search,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet)
router.register("opportunities", OpportunityViewSet, basename="opportunity")
router.register("pipeline", PipelineItemViewSet)
router.register("tasks", TaskViewSet)
router.register("saved-searches", SavedSearchViewSet)
router.register("sync-runs", DataSyncRunViewSet, basename="sync-run")

urlpatterns = [
    path("health/", health),
    path("dashboard/summary/", dashboard_summary),
    path("integrations/status/", integration_status),
    path("live/sam/opportunities/", live_sam_search),
    path("", include(router.urls)),
]
