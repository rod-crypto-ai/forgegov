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
    IntelligenceAlertViewSet,
    OpportunityViewSet,
    OrganizationViewSet,
    ParticipantViewSet,
    PipelineItemViewSet,
    PursuitViewSet,
    SavedSearchViewSet,
    TaskViewSet,
    TeamingRequestViewSet,
    VendorViewSet,
    ProjectRoomViewSet,
    AIConversationViewSet,
    dashboard_summary,
    health,
    integration_status,
    live_sam_search,
    sam_opportunity_detail,
    live_sam_contract_awards,
    live_sam_subaward_search,
    live_sba_subnet_search,
    sam_opportunity_documents,
    live_grants_search,
    live_grants_detail,
    live_usaspending_awards,
    live_usaspending_contract_vehicles,
    federal_forecast_sources,
    global_search,
    state_local_source_directory,
    agency_intelligence,
    vendor_intelligence,
    category_market_intelligence,
    partner_discovery,
    run_saved_search_alerts,
    add_opportunity_to_pipeline,
    ai_chat,
    pipeline_to_pursuit,
    create_saved_search,
    create_workspace_task,
    opportunity_workspace,
    teaming_activity_collection,
    teaming_activity_detail,
    project_room_partner,
    opportunity_documents,
    opportunity_briefing,
    opportunity_document_question,
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
router.register("alerts", IntelligenceAlertViewSet, basename="intelligence-alert")
router.register("project-rooms", ProjectRoomViewSet, basename="project-room")
router.register("ai/conversations", AIConversationViewSet, basename="ai-conversation")

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
    path("live/sam/opportunities/<str:notice_id>/", sam_opportunity_detail),
    path("live/sam/contract-awards/", live_sam_contract_awards),
    path("live/sam/subawards/", live_sam_subaward_search),
    path("live/sba/subnet/", live_sba_subnet_search),
    path("live/sam/opportunities/<str:notice_id>/documents/", sam_opportunity_documents),
    path("live/grants/opportunities/", live_grants_search),
    path("live/grants/opportunities/<str:opportunity_id>/", live_grants_detail),
    path("live/usaspending/awards/", live_usaspending_awards),
    path("live/usaspending/vehicles/", live_usaspending_contract_vehicles),
    path("intelligence/search/", global_search),
    path("intelligence/forecasts/sources/", federal_forecast_sources),
    path("intelligence/state-local/sources/", state_local_source_directory),
    path("intelligence/agencies/", agency_intelligence),
    path("intelligence/vendors/", vendor_intelligence),
    path("intelligence/categories/", category_market_intelligence),
    path("intelligence/partners/", partner_discovery),
    path("workflow/opportunity-to-pipeline/", add_opportunity_to_pipeline),
    path("workflow/pipeline/<int:pipeline_id>/create-pursuit/", pipeline_to_pursuit),
    path("workflow/saved-searches/", create_saved_search),
    path("workflow/saved-searches/evaluate/", run_saved_search_alerts),
    path("workflow/tasks/", create_workspace_task),
    path("workflow/opportunity-workspaces/<str:source_id>/", opportunity_workspace),
    path("workflow/teaming/<int:teaming_id>/activities/", teaming_activity_collection),
    path("workflow/teaming-activities/<int:activity_id>/", teaming_activity_detail),
    path("workflow/project-rooms/<int:room_id>/partners/", project_room_partner),
    path("ai/opportunities/<str:source_id>/documents/", opportunity_documents),
    path("ai/opportunities/<str:source_id>/briefing/", opportunity_briefing),
    path("ai/opportunities/<str:source_id>/ask/", opportunity_document_question),
    path("", include(router.urls)),
]
