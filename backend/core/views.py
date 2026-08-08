from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .notifications import notify_organization_members, send_system_email
from .permissions import ReadOnlyOrContributor, active_membership
from .ai import OpenAIIntegrationError, ask_ai, live_web_status

from .integrations import (
    IntegrationError,
    fetch_grants_opportunity,
    fetch_sam_opportunity_detail,
    search_grants_opportunities,
    search_sam_opportunities,
    search_sam_contract_awards,
    search_sam_subawards,
    search_sba_subnet_opportunities,
    _clean_attachment_name,
    search_federal_forecast_sources,
    search_state_local_sources,
    search_usaspending_contract_vehicles,
    fetch_sam_opportunity_documents,
    search_usaspending_awards,
    usaspending_status,
)
from .models import (
    Agency,
    Award,
    Category,
    Contact,
    ContactGroup,
    DataSyncRun,
    FileRecord,
    IntelligenceAlert,
    Opportunity,
    OpportunityWorkspace,
    Organization,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    Task,
    TeamingRequest,
    ProjectRoom,
    ProjectRoomPartner,
    ProjectRoomMember,
    Membership,
    ProjectRoomTask,
    ProjectRoomComment,
    ProjectRoomNote,
    ProjectRoomFile,
    ProjectRoomActivity,
    CollaborationNotification,
    AIConversation,
    AIMessage,
    OpportunityDocument,
    OpportunityDocumentChunk,
    OpportunityAnalysis,
    TeamingActivity,
    Vendor,
    OrganizationProfile,
    NetworkConnection,
    ProjectRoomInvitation,
    OrganizationJoinRequest,
    AwardSyncRun,
    ConnectorSource,
)
from .serializers import (
    AgencySerializer,
    AwardSerializer,
    CategorySerializer,
    ContactGroupSerializer,
    ContactSerializer,
    DataSyncRunSerializer,
    FileRecordSerializer,
    IntelligenceAlertSerializer,
    OpportunitySerializer,
    OpportunityWorkspaceSerializer,
    OrganizationSerializer,
    ParticipantSerializer,
    PipelineItemSerializer,
    PursuitSerializer,
    SavedSearchSerializer,
    TaskSerializer,
    TeamingRequestSerializer,
    ProjectRoomSerializer,
    ProjectRoomPartnerSerializer,
    ProjectRoomMemberSerializer,
    MembershipSerializer,
    ProjectRoomTaskSerializer,
    ProjectRoomCommentSerializer,
    ProjectRoomNoteSerializer,
    ProjectRoomFileSerializer,
    ProjectRoomActivitySerializer,
    CollaborationNotificationSerializer,
    AIConversationSerializer,
    OpportunityDocumentSerializer,
    OpportunityAnalysisSerializer,
    TeamingActivitySerializer,
    VendorSerializer,
    OrganizationProfileSerializer,
    NetworkConnectionSerializer,
    ProjectRoomInvitationSerializer,
    OrganizationJoinRequestSerializer,
)
from .throttles import OpenAIChatThrottle, SamLiveSearchThrottle
from .document_intelligence import DocumentIngestionError, capture_readiness_summary, chunk_sections, download_document, extract_document, extract_structured_intelligence, sha256
from .capture_intelligence import build_capture_assessment
from .win_strategy import build_win_strategy
from .capture_command_center import build_capture_command_center
from .intelligence.services import connector_health, opportunity_intelligence
from .intelligence.services.award_ingestion import award_intelligence_summary, connector_registry_payload, sync_usaspending_awards


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "forgegov-api", "product": "ForgeGov", "version": "2.8.0-m2.3"})


@api_view(["GET", "POST"])
def award_ingestion(request):
    if request.method == "GET":
        latest = AwardSyncRun.objects.order_by("-created_at")[:20]
        return Response({
            "runs": [{
                "id": row.id,
                "connector_key": row.connector_key,
                "status": row.status,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "pages_processed": row.pages_processed,
                "records_seen": row.records_seen,
                "records_created": row.records_created,
                "records_updated": row.records_updated,
                "errors": row.errors,
            } for row in latest],
            "stored_awards": Award.objects.filter(source="usaspending.gov").count(),
        })
    membership = active_membership(request.user)
    if not membership or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return Response({"detail": "Only workspace owners and administrators can start award ingestion."}, status=403)
    try:
        run = sync_usaspending_awards(
            start_date=request.data.get("start_date"),
            end_date=request.data.get("end_date"),
            pages=int(request.data.get("pages") or 1),
            limit=int(request.data.get("limit") or 100),
            keyword=str(request.data.get("keyword") or ""),
            agency=str(request.data.get("agency") or ""),
            naics=str(request.data.get("naics") or ""),
        )
    except (ValueError, IntegrationError) as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response({
        "id": run.id,
        "status": run.status,
        "records_seen": run.records_seen,
        "records_created": run.records_created,
        "records_updated": run.records_updated,
        "errors": run.errors,
    }, status=201)


@api_view(["GET"])
def connector_registry_view(request):
    probe = _truthy(request.query_params.get("probe"))
    return Response(connector_registry_payload(probe=probe))


@api_view(["GET"])
def award_intelligence_view(request):
    return Response(award_intelligence_summary(
        agency=str(request.query_params.get("agency") or ""),
        naics=str(request.query_params.get("naics") or ""),
        psc=str(request.query_params.get("psc") or ""),
        recipient=str(request.query_params.get("recipient") or ""),
        limit=max(1, min(int(request.query_params.get("limit") or 10), 50)),
    ))


@api_view(["GET"])
def integration_status(request):
    probe = _truthy(request.query_params.get("probe"))
    latest_sync = DataSyncRun.objects.filter(source="sam.gov").first()
    latest_usa_sync = DataSyncRun.objects.filter(source="usaspending.gov").first()
    web_status = live_web_status(probe=probe)
    return Response({
        "sam_gov": {
            "configured": bool(settings.SAM_GOV_API_KEY),
            "base_url": settings.SAM_GOV_BASE_URL,
            "latest_sync": DataSyncRunSerializer(latest_sync).data if latest_sync else None,
        },
        "usaspending": {**usaspending_status(probe=probe), "latest_sync": DataSyncRunSerializer(latest_usa_sync).data if latest_usa_sync else None, "stored_awards": Award.objects.filter(source="usaspending.gov").count()},
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
            "model": settings.OPENAI_MODEL,
            "base_url": settings.OPENAI_API_BASE_URL,
        },
        "email": {
            "backend": settings.EMAIL_BACKEND,
            "configured": settings.EMAIL_BACKEND != "django.core.mail.backends.console.EmailBackend" and bool(getattr(settings, "DEFAULT_FROM_EMAIL", "")),
            "from_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        },
        "ai": {
            "provider": settings.AI_PROVIDER,
            "model": settings.OLLAMA_MODEL if settings.AI_PROVIDER == "ollama" else settings.OPENAI_MODEL,
            "configured": bool(settings.OLLAMA_BASE_URL) if settings.AI_PROVIDER == "ollama" else bool(settings.OPENAI_API_KEY),
            "web_search": bool(web_status.get("reachable")) if probe else bool(web_status.get("configured")),
            "web_search_configured": bool(web_status.get("configured")),
            "web_search_reachable": web_status.get("reachable"),
            "web_search_status": web_status.get("status"),
        },
        "expansion": {
            "forecast_directory": "https://www.acquisition.gov/procurement-forecasts",
            "subnet": settings.SBA_SUBNET_URL,
            "sam_subawards_configured": bool(settings.SAM_GOV_API_KEY),
            "stored_contract_vehicles": Award.objects.filter(award_type=Award.AwardType.VEHICLE).count(),
        },
    })


@api_view(["GET"])
def intelligence_connectors(request):
    probe = _truthy(request.query_params.get("probe"))
    return Response(connector_health(probe=probe))


@api_view(["GET"])
def opportunity_intelligence_view(request, source_id):
    refresh = _truthy(request.query_params.get("refresh"))
    return Response(opportunity_intelligence(source_id, refresh=refresh))


@api_view(["GET"])
def dashboard_summary(request):
    organization = _request_organization(request)
    pipeline_base = PipelineItem.objects.filter(organization=organization)
    pursuit_base = Pursuit.objects.filter(organization=organization)
    task_base = Task.objects.filter(organization=organization)
    pipeline_counts = {
        row["stage"]: row["count"]
        for row in pipeline_base.values("stage").annotate(count=Count("id"))
    }
    pursuit_counts = {
        row["stage"]: row["count"]
        for row in pursuit_base.values("stage").annotate(count=Count("id"))
    }
    weighted_expression = ExpressionWrapper(
        F("estimated_value") * F("probability_of_win") / 100,
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )
    weighted_value = pursuit_base.exclude(estimated_value__isnull=True).aggregate(total=Sum(weighted_expression))["total"] or 0
    award_totals = Award.objects.aggregate(total=Sum("obligated_amount"))
    now = timezone.now()
    return Response({
        "opportunities": {
            "total": Opportunity.objects.count(),
            "active": Opportunity.objects.filter(active=True).count(),
        },
        "awards": {
            "total": Award.objects.count(),
            "obligated_total": award_totals["total"] or 0,
        },
        "pipeline": {
            "total": pipeline_base.count(),
            "by_stage": pipeline_counts,
            "weighted_value": weighted_value,
        },
        "pursuits": {
            "total": pursuit_base.count(),
            "by_stage": pursuit_counts,
        },
        "tasks": {
            "open": task_base.filter(completed=False).count(),
            "completed": task_base.filter(completed=True).count(),
            "overdue": task_base.filter(completed=False, due_at__lt=now).count(),
        },
        "alerts": {
            "unread": IntelligenceAlert.objects.filter(organization=organization, read=False, dismissed=False).count(),
            "total": IntelligenceAlert.objects.filter(organization=organization, dismissed=False).count(),
        },
        "contacts": Contact.objects.filter(organization=organization).count(),
        "vendors": Vendor.objects.count(),
        "agencies": Agency.objects.count(),
        "workspaces": 1,
        "saved_searches": SavedSearch.objects.filter(organization=organization, enabled=True).count(),
        "files": FileRecord.objects.filter(organization=organization).count(),
    })


@api_view(["POST"])
@throttle_classes([OpenAIChatThrottle])
def ai_chat(request):
    message = str(request.data.get("message") or "").strip()
    if not message:
        return Response({"detail": "A message is required."}, status=status.HTTP_400_BAD_REQUEST)
    if len(message) > 8000:
        return Response({"detail": "The message is too long. Limit requests to 8,000 characters."}, status=status.HTTP_400_BAD_REQUEST)
    history = request.data.get("history") or []
    if not isinstance(history, list):
        return Response({"detail": "history must be a list."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        organization = _request_organization(request)
        conversation_id = request.data.get("conversation_id")
        conversation = None
        if conversation_id:
            conversation = AIConversation.objects.filter(pk=conversation_id, organization=organization).first()
            if not conversation:
                return Response({"detail": "Conversation not found in this workspace."}, status=status.HTTP_404_NOT_FOUND)
        elif request.data.get("persist"):
            project_room = None
            project_room_id = request.data.get("project_room_id")
            if project_room_id:
                project_room = ProjectRoom.objects.filter(Q(owner_organization=organization) | Q(partners__organization=organization), pk=project_room_id).distinct().first()
                if not project_room:
                    return Response({"detail": "Project Room not found or not accessible."}, status=status.HTTP_404_NOT_FOUND)
            conversation = AIConversation.objects.create(organization=organization, project_room=project_room, title=message[:120], created_by=request.user)
        if conversation:
            AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.USER, content=message)
        result = ask_ai(message=message, history=history, organization=organization)
        if conversation:
            AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.ASSISTANT, content=result.get("answer", ""), sources=result.get("sources") or [], model=result.get("model", ""), provider=result.get("provider", ""))
            result["conversation_id"] = conversation.id
        return Response(result)
    except Organization.DoesNotExist:
        return Response({"detail": "An active workspace membership is required."}, status=status.HTTP_403_FORBIDDEN)
    except OpenAIIntegrationError as exc:
        return Response({"detail": str(exc)}, status=exc.status_code)


@api_view(["GET"])
@throttle_classes([SamLiveSearchThrottle])
def live_sam_search(request):
    try:
        data = search_sam_opportunities(
            keyword=request.query_params.get("q", ""),
            limit=int(request.query_params.get("limit", 25)),
            offset=int(request.query_params.get("offset", 0)),
            posted_from=request.query_params.get("posted_from"),
            posted_to=request.query_params.get("posted_to"),
            procurement_type=request.query_params.get("ptype", ""),
            solicitation_number=request.query_params.get("solnum", ""),
            notice_id=request.query_params.get("notice_id", ""),
            agency=request.query_params.get("agency", ""),
            naics=request.query_params.get("naics", ""),
            psc=request.query_params.get("psc", ""),
            state=request.query_params.get("state", ""),
            set_aside=request.query_params.get("set_aside", ""),
            response_from=request.query_params.get("response_from", ""),
            response_to=request.query_params.get("response_to", ""),
            opportunity_status=request.query_params.get("status", ""),
            persist=_truthy(request.query_params.get("persist")),
        )
        return Response(data)
    except IntegrationError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if not settings.SAM_GOV_API_KEY else status.HTTP_502_BAD_GATEWAY
        return Response({"detail": str(exc)}, status=code)
    except (TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@throttle_classes([SamLiveSearchThrottle])
def live_sam_contract_awards(request):
    try:
        data = search_sam_contract_awards(
            record_type=request.query_params.get("record_type", "contracts"),
            keyword=request.query_params.get("q", ""),
            agency=request.query_params.get("agency", ""),
            naics=request.query_params.get("naics", ""),
            psc=request.query_params.get("psc", ""),
            state=request.query_params.get("state", ""),
            fiscal_year=request.query_params.get("fiscal_year", ""),
            limit=int(request.query_params.get("limit", 25)),
            offset=int(request.query_params.get("offset", 0)),
        )
        return Response(data)
    except (IntegrationError, TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def sam_opportunity_documents(request, notice_id):
    try:
        return Response(fetch_sam_opportunity_documents(notice_id))
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET", "POST"])
def live_usaspending_awards(request):
    params = request.query_params if request.method == "GET" else request.data
    try:
        data = search_usaspending_awards(
            keyword=params.get("q", ""),
            recipient=params.get("recipient", ""),
            agency=params.get("agency", ""),
            naics=params.get("naics", ""),
            start_date=params.get("start_date") or None,
            end_date=params.get("end_date") or None,
            page=int(params.get("page", 1)),
            limit=int(params.get("limit", 25)),
            persist=_truthy(params.get("persist")),
        )
        return Response(data)
    except (IntegrationError, TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _request_organization(request) -> Organization:
    membership = active_membership(request.user)
    if not membership:
        raise Organization.DoesNotExist
    return membership.organization


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def add_opportunity_to_pipeline(request):
    source_id = str(request.data.get("source_id") or request.data.get("notice_id") or "").strip()
    if not source_id:
        return Response({"detail": "source_id is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        opportunity = Opportunity.objects.get(source_id=source_id)
    except Opportunity.DoesNotExist:
        return Response({"detail": "Search with Store results enabled before adding this opportunity."}, status=status.HTTP_404_NOT_FOUND)
    organization = _request_organization(request)
    requested_stage = str(request.data.get("stage") or PipelineItem.Stage.REVIEWING)
    valid_stages = {value for value, _ in PipelineItem.Stage.choices}
    if requested_stage not in valid_stages:
        return Response({"detail": "A valid pipeline stage is required."}, status=status.HTTP_400_BAD_REQUEST)
    item, created = PipelineItem.objects.get_or_create(
        organization=organization, opportunity=opportunity,
        defaults={"stage": requested_stage, "owner": request.user, "next_action": "Complete qualification review"},
    )
    if not created and request.data.get("stage"):
        item.stage = requested_stage
        item.save(update_fields=["stage", "updated_at"])
    return Response(PipelineItemSerializer(item).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def pipeline_to_pursuit(request, pipeline_id: int):
    try:
        item = PipelineItem.objects.select_related("opportunity", "organization").get(pk=pipeline_id, organization=_request_organization(request))
    except PipelineItem.DoesNotExist:
        return Response({"detail": "Pipeline item not found."}, status=status.HTTP_404_NOT_FOUND)
    pursuit, created = Pursuit.objects.get_or_create(
        organization=item.organization, opportunity=item.opportunity,
        defaults={
            "title": item.opportunity.title, "stage": Pursuit.Stage.QUALIFY,
            "estimated_value": item.estimated_value, "probability_of_win": item.probability_of_win,
            "due_date": item.opportunity.response_deadline, "next_action": item.next_action or "Build capture plan",
            "notes": item.notes,
        },
    )
    if item.stage not in {PipelineItem.Stage.AWARDED, PipelineItem.Stage.LOST, PipelineItem.Stage.NO_BID}:
        item.stage = PipelineItem.Stage.CAPTURE
        item.save(update_fields=["stage", "updated_at"])
    return Response(PursuitSerializer(pursuit).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["GET", "PATCH"])
@permission_classes([ReadOnlyOrContributor])
def opportunity_workspace(request, source_id: str):
    organization = _request_organization(request)
    opportunity = Opportunity.objects.filter(source_id=source_id).first()
    if not opportunity:
        return Response({"detail": "Open the live opportunity once with Store results enabled before using its workspace."}, status=status.HTTP_404_NOT_FOUND)
    workspace, _ = OpportunityWorkspace.objects.get_or_create(organization=organization, opportunity=opportunity)
    if request.method == "PATCH":
        serializer = OpportunityWorkspaceSerializer(workspace, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(OpportunityWorkspaceSerializer(workspace, context={"request": request}).data)


@api_view(["GET", "POST"])
@permission_classes([ReadOnlyOrContributor])
def teaming_activity_collection(request, teaming_id: int):
    organization = _request_organization(request)
    teaming = TeamingRequest.objects.filter(pk=teaming_id, organization=organization).first()
    if not teaming:
        return Response({"detail": "Teaming lead not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        rows = TeamingActivity.objects.filter(organization=organization, teaming_request=teaming)
        return Response(TeamingActivitySerializer(rows, many=True, context={"request": request}).data)
    payload = request.data.copy()
    payload["teaming_request"] = teaming.id
    serializer = TeamingActivitySerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=organization)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([ReadOnlyOrContributor])
def teaming_activity_detail(request, activity_id: int):
    organization = _request_organization(request)
    activity = TeamingActivity.objects.filter(pk=activity_id, organization=organization).first()
    if not activity:
        return Response({"detail": "Teaming activity not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        activity.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = TeamingActivitySerializer(activity, data=request.data, partial=True, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def create_saved_search(request):
    name = str(request.data.get("name") or "").strip()
    filters = request.data.get("filters") or {}
    if not name:
        return Response({"detail": "A saved-search name is required."}, status=status.HTTP_400_BAD_REQUEST)
    record = SavedSearch.objects.create(organization=_request_organization(request), owner=request.user, name=name, filters=filters, alert_frequency=request.data.get("alert_frequency") or "daily", enabled=True)
    return Response(SavedSearchSerializer(record).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def create_workspace_task(request):
    title = str(request.data.get("title") or "").strip()
    if not title:
        return Response({"detail": "Task title is required."}, status=status.HTTP_400_BAD_REQUEST)
    organization = _request_organization(request)
    pipeline_item = None
    pipeline_id = request.data.get("pipeline_item")
    if pipeline_id:
        pipeline_item = PipelineItem.objects.filter(pk=pipeline_id, organization=organization).first()
        if not pipeline_item:
            return Response({"detail": "Pipeline item not found in this workspace."}, status=status.HTTP_400_BAD_REQUEST)
    record = Task.objects.create(organization=organization, assigned_to=request.user, pipeline_item=pipeline_item, title=title, description=request.data.get("description") or "", due_at=request.data.get("due_at") or None)
    return Response(TaskSerializer(record).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def live_grants_search(request):
    try:
        data = search_grants_opportunities(
            keyword=request.query_params.get("q", ""),
            opportunity_number=request.query_params.get("opportunity_number", ""),
            agencies=request.query_params.get("agency", ""),
            statuses=request.query_params.get("statuses", "forecasted|posted"),
            aln=request.query_params.get("aln", ""),
            funding_categories=request.query_params.get("funding_categories", ""),
            eligibilities=request.query_params.get("eligibilities", ""),
            funding_instruments=request.query_params.get("funding_instruments", ""),
            sort_by=request.query_params.get("sort_by", ""),
            limit=int(request.query_params.get("limit", 25)),
            offset=int(request.query_params.get("offset", 0)),
            persist=_truthy(request.query_params.get("persist", "true")),
        )
        return Response(data)
    except (IntegrationError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
def live_grants_detail(request, opportunity_id: str):
    try:
        return Response(fetch_grants_opportunity(opportunity_id, persist=True))
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class OrganizationScopedViewSetMixin:
    permission_classes = [ReadOnlyOrContributor]

    def get_organization(self):
        return _request_organization(self.request)

    def scope_queryset(self, queryset):
        return queryset.filter(organization=self.get_organization())

    def perform_create(self, serializer):
        extra = {"organization": self.get_organization()}
        model = serializer.Meta.model
        field_names = {field.name for field in model._meta.fields}
        if "owner" in field_names and not serializer.validated_data.get("owner"):
            extra["owner"] = self.request.user
        if "assigned_to" in field_names and not serializer.validated_data.get("assigned_to"):
            extra["assigned_to"] = self.request.user
        serializer.save(**extra)


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [ReadOnlyOrContributor]

    def get_queryset(self):
        return Organization.objects.filter(pk=_request_organization(self.request).pk)


class OpportunityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OpportunitySerializer

    def get_queryset(self):
        queryset = Opportunity.objects.all()
        search = self.request.query_params.get("search")
        agency = self.request.query_params.get("agency")
        naics = self.request.query_params.get("naics")
        psc = self.request.query_params.get("psc")
        active = self.request.query_params.get("active")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(solicitation_number__icontains=search)
            )
        if agency:
            queryset = queryset.filter(Q(agency__icontains=agency) | Q(subagency__icontains=agency) | Q(office__icontains=agency))
        if naics:
            queryset = queryset.filter(naics_code=naics)
        if psc:
            queryset = queryset.filter(psc_code=psc)
        if active is not None:
            queryset = queryset.filter(active=_truthy(active))
        return queryset


class PipelineItemViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PipelineItemSerializer
    def get_queryset(self):
        return self.scope_queryset(PipelineItem.objects.select_related("opportunity", "organization", "owner"))


class PursuitViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PursuitSerializer

    def get_queryset(self):
        queryset = self.scope_queryset(Pursuit.objects.select_related("opportunity", "organization", "owner"))
        stage = self.request.query_params.get("stage")
        search = self.request.query_params.get("search")
        if stage:
            queryset = queryset.filter(stage=stage)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(next_action__icontains=search) | Q(incumbent__icontains=search))
        return queryset


class TaskViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    def get_queryset(self):
        return self.scope_queryset(Task.objects.select_related("organization", "pipeline_item", "assigned_to"))


class SavedSearchViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SavedSearchSerializer
    def get_queryset(self):
        return self.scope_queryset(SavedSearch.objects.select_related("organization", "owner"))


class DataSyncRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataSyncRun.objects.all()
    serializer_class = DataSyncRunSerializer


class AgencyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AgencySerializer

    def get_queryset(self):
        queryset = Agency.objects.all()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(agency_code__icontains=search) | Q(parent_name__icontains=search))
        return queryset


class VendorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VendorSerializer

    def get_queryset(self):
        queryset = Vendor.objects.all()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(uei__icontains=search) | Q(cage_code__icontains=search))
        return queryset


class AwardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AwardSerializer

    def get_queryset(self):
        queryset = Award.objects.all()
        award_type = self.request.query_params.get("award_type")
        search = self.request.query_params.get("search")
        agency = self.request.query_params.get("agency")
        if award_type:
            queryset = queryset.filter(award_type=award_type)
        if search:
            queryset = queryset.filter(
                Q(award_number__icontains=search)
                | Q(description__icontains=search)
                | Q(recipient_name__icontains=search)
            )
        if agency:
            queryset = queryset.filter(Q(awarding_agency__icontains=agency) | Q(funding_agency__icontains=agency))
        return queryset


class ContactViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ContactSerializer

    def get_queryset(self):
        queryset = self.scope_queryset(Contact.objects.select_related("organization", "relationship_owner"))
        search = self.request.query_params.get("search")
        contact_type = self.request.query_params.get("contact_type")
        if contact_type:
            queryset = queryset.filter(contact_type=contact_type)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(title__icontains=search)
                | Q(email__icontains=search)
                | Q(agency_name__icontains=search)
                | Q(vendor_name__icontains=search)
            )
        return queryset


class ContactGroupViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ContactGroupSerializer
    def get_queryset(self):
        return self.scope_queryset(ContactGroup.objects.prefetch_related("contacts"))


class TeamingRequestViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TeamingRequestSerializer

    def get_queryset(self):
        queryset = self.scope_queryset(TeamingRequest.objects.select_related("organization", "pursuit"))
        request_status = self.request.query_params.get("status")
        if request_status:
            queryset = queryset.filter(status=request_status)
        return queryset


class FileRecordViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = FileRecordSerializer

    def get_queryset(self):
        queryset = self.scope_queryset(FileRecord.objects.select_related("organization", "opportunity", "pursuit"))
        source = self.request.query_params.get("source")
        if source:
            queryset = queryset.filter(source=source)
        return queryset


class ParticipantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParticipantSerializer

    def get_queryset(self):
        queryset = Participant.objects.all()
        participant_type = self.request.query_params.get("participant_type")
        if participant_type:
            queryset = queryset.filter(participant_type=participant_type)
        return queryset


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.all()
        category_type = self.request.query_params.get("category_type")
        search = self.request.query_params.get("search")
        if category_type:
            queryset = queryset.filter(category_type=category_type)
        if search:
            queryset = queryset.filter(Q(code__icontains=search) | Q(title__icontains=search) | Q(description__icontains=search))
        return queryset


@api_view(["GET"])
@throttle_classes([SamLiveSearchThrottle])
def sam_opportunity_detail(request, notice_id: str):
    try:
        return Response(fetch_sam_opportunity_detail(notice_id))
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET", "POST"])
def live_usaspending_contract_vehicles(request):
    params = request.query_params if request.method == "GET" else request.data
    try:
        return Response(search_usaspending_contract_vehicles(
            keyword=params.get("q", ""),
            recipient=params.get("recipient", ""),
            agency=params.get("agency", ""),
            naics=params.get("naics", ""),
            start_date=params.get("start_date") or None,
            end_date=params.get("end_date") or None,
            page=int(params.get("page", 1)),
            limit=int(params.get("limit", 25)),
            persist=_truthy(params.get("persist")),
        ))
    except (IntegrationError, TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def federal_forecast_sources(request):
    return Response(search_federal_forecast_sources(query=request.query_params.get("q", "")))


@api_view(["GET"])
def state_local_source_directory(request):
    return Response(search_state_local_sources(
        query=request.query_params.get("q", ""),
        state=request.query_params.get("state", ""),
    ))


@api_view(["GET"])
@throttle_classes([SamLiveSearchThrottle])
def live_sam_subaward_search(request):
    try:
        return Response(search_sam_subawards(
            piid=request.query_params.get("piid", ""),
            referenced_idv=request.query_params.get("referenced_idv", ""),
            agency_id=request.query_params.get("agency_id", ""),
            from_date=request.query_params.get("from_date", ""),
            to_date=request.query_params.get("to_date", ""),
            page=int(request.query_params.get("page", 0)),
            limit=int(request.query_params.get("limit", 25)),
        ))
    except (IntegrationError, TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def live_sba_subnet_search(request):
    try:
        return Response(search_sba_subnet_opportunities(
            query=request.query_params.get("q", ""),
            state=request.query_params.get("state", ""),
            page=int(request.query_params.get("page", 0)),
            page_size=int(request.query_params.get("page_size", 20)),
        ))
    except IntegrationError as exc:
        return Response({"results": [], "status": "unavailable", "reachable": False, "warning": str(exc), "page": 0, "has_next": False})


@api_view(["GET"])
def global_search(request):
    """Unified organization-aware search across ForgeGov intelligence and workspaces."""
    query = str(request.query_params.get("q") or "").strip()
    if len(query) < 2:
        return Response({"query": query, "results": [], "groups": {}})
    limit = min(max(int(request.query_params.get("limit", 10)), 1), 30)
    organization = _request_organization(request)
    results = []

    def add(result_type, obj_id, title, subtitle, href, *, group="Intelligence", metadata=None):
        results.append({
            "type": result_type,
            "id": obj_id,
            "title": title,
            "subtitle": subtitle or "",
            "href": href,
            "group": group,
            "metadata": metadata or {},
        })

    for item in Opportunity.objects.filter(
        Q(title__icontains=query) | Q(solicitation_number__icontains=query) | Q(agency__icontains=query) | Q(description__icontains=query)
    ).order_by("-posted_date")[:limit]:
        if item.source == "grants.gov" or str(item.source_id).startswith("grants.gov:"):
            grant_id = str(item.source_id).replace("grants.gov:", "", 1)
            add("grant", item.source_id or item.id, item.title, item.solicitation_number or item.agency, f"/opportunities/federal-grants/{grant_id}" if grant_id else "/opportunities/federal-grants", group="Opportunities")
        else:
            add("opportunity", item.source_id or item.id, item.title, item.solicitation_number or item.agency, f"/opportunities/federal-contracts/{item.source_id}" if item.source_id else "/opportunities/federal-contracts", group="Opportunities")

    for item in PipelineItem.objects.filter(organization=organization).filter(
        Q(opportunity__title__icontains=query) | Q(opportunity__solicitation_number__icontains=query) | Q(notes__icontains=query) | Q(next_action__icontains=query)
    ).select_related("opportunity")[:limit]:
        add("pipeline", item.id, item.opportunity.title, f"{item.get_stage_display()} · {item.opportunity.solicitation_number or item.opportunity.agency}", "/capture/pipelines", group="Capture")

    for item in Pursuit.objects.filter(organization=organization).filter(Q(title__icontains=query) | Q(notes__icontains=query) | Q(next_action__icontains=query))[:limit]:
        add("pursuit", item.id, item.title, item.get_stage_display(), "/capture/pursuits", group="Capture")

    for item in Task.objects.filter(organization=organization).filter(Q(title__icontains=query) | Q(description__icontains=query))[:limit]:
        add("task", item.id, item.title, "Completed" if item.completed else "Open task", "/capture/tasks", group="Work")

    room_filter = Q(owner_organization=organization) | Q(partners__organization=organization)
    for item in ProjectRoom.objects.filter(room_filter).filter(Q(name__icontains=query) | Q(description__icontains=query)).distinct()[:limit]:
        add("project_room", item.id, item.name, item.get_status_display(), f"/project-rooms/{item.id}", group="Collaboration")

    for item in OpportunityDocument.objects.filter(organization=organization).filter(Q(file_name__icontains=query) | Q(chunks__text__icontains=query)).distinct()[:limit]:
        add("document", item.id, item.file_name, item.opportunity.title, f"/opportunities/federal-contracts/{item.opportunity.source_id}", group="Documents")

    for item in OrganizationProfile.objects.filter(is_public=True).filter(
        Q(organization__name__icontains=query) | Q(tagline__icontains=query) | Q(description__icontains=query) | Q(capabilities__icontains=query)
    ).select_related("organization")[:limit]:
        if item.organization_id != organization.id:
            add("company", item.organization_id, item.organization.name, item.tagline or ", ".join(item.capabilities[:3]), "/network", group="Network")

    for item in Vendor.objects.filter(Q(name__icontains=query) | Q(uei__icontains=query) | Q(cage_code__icontains=query)).order_by("name")[:limit]:
        add("vendor", item.id, item.name, " · ".join(filter(None,[item.uei,item.cage_code,item.state])), f"/participants/vendors/profile?id={item.id}", group="Market Intelligence")
    for item in Agency.objects.filter(Q(name__icontains=query) | Q(agency_code__icontains=query)).order_by("name")[:limit]:
        add("agency", item.id, item.name, item.agency_code, f"/intelligence/agency/{item.name}", group="Market Intelligence")
    for item in Award.objects.filter(Q(recipient_name__icontains=query) | Q(award_number__icontains=query) | Q(description__icontains=query) | Q(awarding_agency__icontains=query)).order_by("-start_date", "-updated_at")[:limit]:
        add("award", item.id, item.description or item.award_number or "Federal award", f"{item.recipient_name} · {item.awarding_agency}".strip(" ·"), f"/intelligence/award/{item.award_number or item.source_id or item.id}", group="Awards")

    groups = {}
    for row in results:
        groups.setdefault(row["group"], 0)
        groups[row["group"]] += 1
    return Response({"query": query, "results": results[:limit * 8], "groups": groups})


@api_view(["GET"])
def command_center(request):
    """Organization-scoped operating picture for capture, collaboration, deadlines, and alerts."""
    organization = _request_organization(request)
    now = timezone.now()
    today = now.date()
    room_filter = Q(owner_organization=organization) | Q(partners__organization=organization)
    rooms = ProjectRoom.objects.filter(room_filter).distinct()

    deadlines = []
    for task in Task.objects.filter(organization=organization, completed=False, due_at__isnull=False).order_by("due_at")[:8]:
        deadlines.append({"type":"task","title":task.title,"due_at":task.due_at.isoformat(),"href":"/capture/tasks","overdue":task.due_at < now})
    for task in ProjectRoomTask.objects.filter(Q(project_room__owner_organization=organization) | Q(project_room__partners__organization=organization, visibility=ProjectRoomTask.Visibility.SHARED)).distinct().exclude(status=ProjectRoomTask.Status.DONE).filter(due_date__isnull=False).select_related("project_room").order_by("due_date")[:8]:
        deadlines.append({"type":"project_task","title":task.title,"subtitle":task.project_room.name,"due_at":task.due_date.isoformat(),"href":f"/project-rooms/{task.project_room_id}","overdue":task.due_date < today})
    deadlines = sorted(deadlines, key=lambda row: row["due_at"])[:10]

    activity = []
    for row in ProjectRoomActivity.objects.filter(Q(project_room__owner_organization=organization) | Q(project_room__partners__organization=organization, visibility=ProjectRoomNote.Visibility.SHARED)).distinct().select_related("project_room", "actor").order_by("-created_at")[:10]:
        activity.append({"type":"project_room","title":row.summary,"subtitle":row.project_room.name,"created_at":row.created_at.isoformat(),"href":f"/project-rooms/{row.project_room_id}"})
    for row in IntelligenceAlert.objects.filter(organization=organization, dismissed=False).order_by("-created_at")[:8]:
        activity.append({"type":"alert","title":row.title,"subtitle":row.summary[:180],"created_at":row.created_at.isoformat(),"href":"/capture/alerts"})
    activity = sorted(activity, key=lambda row: row["created_at"], reverse=True)[:12]

    pipeline = PipelineItem.objects.filter(organization=organization)
    open_tasks = Task.objects.filter(organization=organization, completed=False)
    active_rooms = rooms.filter(status__in=[ProjectRoom.Status.PLANNING, ProjectRoom.Status.ACTIVE])
    pending_connections = NetworkConnection.objects.filter(Q(requester=organization) | Q(recipient=organization), status=NetworkConnection.Status.PENDING).count()
    pending_room_invites = ProjectRoomInvitation.objects.filter(invited_organization=organization, status=ProjectRoomInvitation.Status.PENDING).count()
    unread_alerts = IntelligenceAlert.objects.filter(organization=organization, read=False, dismissed=False).count()
    overdue = open_tasks.filter(due_at__lt=now).count() + ProjectRoomTask.objects.filter(Q(project_room__owner_organization=organization) | Q(project_room__partners__organization=organization, visibility=ProjectRoomTask.Visibility.SHARED)).distinct().exclude(status=ProjectRoomTask.Status.DONE).filter(due_date__lt=today).count()

    insights = []
    if overdue:
        insights.append({"severity":"high","title":f"{overdue} overdue action{'s' if overdue != 1 else ''}","detail":"Clear overdue work before adding new pursuit commitments.","href":"/capture/tasks"})
    if pending_connections or pending_room_invites:
        insights.append({"severity":"medium","title":"Partner responses need attention","detail":f"{pending_connections} connection request(s) and {pending_room_invites} Project Room invitation(s) are pending.","href":"/network?tab=invitations"})
    if unread_alerts:
        insights.append({"severity":"info","title":f"{unread_alerts} unread intelligence alert{'s' if unread_alerts != 1 else ''}","detail":"Review new opportunity matches and deadline signals.","href":"/capture/alerts"})
    if not insights:
        insights.append({"severity":"success","title":"Workspace is under control","detail":"No overdue work or pending collaboration decisions were detected.","href":"/"})

    weighted_pipeline = Decimal("0")
    for item in pipeline.exclude(stage__in=[PipelineItem.Stage.LOST, PipelineItem.Stage.NO_BID, PipelineItem.Stage.ARCHIVED]):
        if item.estimated_value:
            weighted_pipeline += item.estimated_value * Decimal(item.probability_of_win or 0) / Decimal("100")

    recent_awards = Award.objects.order_by("-source_updated_at", "-updated_at")
    recent_award_count = recent_awards.filter(source_updated_at__gte=now - timedelta(days=30)).count()
    latest_sync = AwardSyncRun.objects.filter(connector_key="usaspending").order_by("-created_at").first()
    connector_rows = ConnectorSource.objects.filter(enabled=True).order_by("scope", "name")
    connector_health = {
        "healthy": connector_rows.filter(last_status__in=["healthy", "reachable", "ok"]).count(),
        "attention": connector_rows.exclude(last_status__in=["healthy", "reachable", "ok", "not_checked"]).count(),
        "total": connector_rows.count(),
    }
    top_award_recipients = list(
        Award.objects.exclude(recipient_name="")
        .values("recipient_name")
        .annotate(awards=Count("id"), obligated=Sum("obligated_amount"))
        .order_by("-obligated")[:5]
    )

    return Response({
        "metrics": {
            "pipeline": pipeline.count(),
            "active_rooms": active_rooms.count(),
            "open_tasks": open_tasks.count(),
            "overdue": overdue,
            "unread_alerts": unread_alerts,
            "pending_invitations": pending_connections + pending_room_invites,
            "weighted_pipeline": float(weighted_pipeline),
        },
        "intelligence": {
            "recent_awards_30d": recent_award_count,
            "stored_awards": Award.objects.count(),
            "latest_award_sync": latest_sync.completed_at.isoformat() if latest_sync and latest_sync.completed_at else None,
            "latest_award_sync_status": latest_sync.status if latest_sync else "not_run",
            "connectors": connector_health,
            "top_award_recipients": top_award_recipients,
        },
        "deadlines": deadlines,
        "activity": activity,
        "insights": insights,
        "quick_actions": [
            {"label":"Find opportunities","href":"/opportunities/federal-contracts"},
            {"label":"Open pipeline","href":"/capture/pipelines"},
            {"label":"Create Project Room","href":"/project-rooms"},
            {"label":"Find partners","href":"/network"},
            {"label":"Ask ForgeGov AI","href":"/assistant"},
        ],
    })


@api_view(["GET"])
def agency_intelligence(request):
    name = str(request.query_params.get("name") or request.query_params.get("q") or "").strip()
    base = Agency.objects.all()
    if name:
        base = base.filter(name__icontains=name)
    agencies = list(base.order_by("name")[:50])
    results = []
    for agency in agencies:
        awards = Award.objects.filter(Q(awarding_agency=agency.name) | Q(funding_agency=agency.name))
        opportunities = Opportunity.objects.filter(Q(agency=agency.name) | Q(subagency=agency.name) | Q(organization_path__icontains=agency.name))
        top_vendors = list(
            awards.exclude(recipient_name="")
            .values("recipient_name")
            .annotate(obligated=Sum("obligated_amount"), awards=Count("id"))
            .order_by("-obligated")[:5]
        )
        top_naics = list(
            awards.exclude(naics_code="")
            .values("naics_code")
            .annotate(obligated=Sum("obligated_amount"), awards=Count("id"))
            .order_by("-obligated")[:5]
        )
        results.append({
            "id": agency.id,
            "name": agency.name,
            "agency_code": agency.agency_code,
            "website": agency.website,
            "award_count": awards.count(),
            "obligated_amount": awards.aggregate(total=Sum("obligated_amount"))["total"] or 0,
            "active_opportunities": opportunities.filter(active=True).count(),
            "top_vendors": top_vendors,
            "top_naics": top_naics,
            "recent_awards": AwardSerializer(awards.order_by("-start_date", "-updated_at")[:5], many=True).data,
            "recent_opportunities": OpportunitySerializer(opportunities.order_by("-posted_date")[:5], many=True).data,
        })
    return Response({"total_records": len(results), "results": results})


@api_view(["GET"])
def vendor_intelligence(request):
    name = str(request.query_params.get("name") or request.query_params.get("q") or "").strip()
    base = Vendor.objects.all()
    if name:
        base = base.filter(Q(name__icontains=name) | Q(uei__icontains=name) | Q(cage_code__icontains=name))
    vendors = list(base.order_by("name")[:50])
    results = []
    for vendor in vendors:
        awards = Award.objects.filter(recipient_name=vendor.name)
        top_agencies = list(
            awards.exclude(awarding_agency="")
            .values("awarding_agency")
            .annotate(obligated=Sum("obligated_amount"), awards=Count("id"))
            .order_by("-obligated")[:5]
        )
        top_naics = list(
            awards.exclude(naics_code="")
            .values("naics_code")
            .annotate(obligated=Sum("obligated_amount"), awards=Count("id"))
            .order_by("-obligated")[:5]
        )
        results.append({
            "id": vendor.id,
            "name": vendor.name,
            "uei": vendor.uei,
            "cage_code": vendor.cage_code,
            "city": vendor.city,
            "state": vendor.state,
            "website": vendor.website,
            "socioeconomic_statuses": vendor.socioeconomic_statuses,
            "naics_codes": vendor.naics_codes,
            "award_count": awards.count(),
            "obligated_amount": awards.aggregate(total=Sum("obligated_amount"))["total"] or 0,
            "top_agencies": top_agencies,
            "top_naics": top_naics,
            "recent_awards": AwardSerializer(awards.order_by("-start_date", "-updated_at")[:10], many=True).data,
            "related_opportunities": OpportunitySerializer(
                Opportunity.objects.filter(
                    Q(naics_code__in=[str(code) for code in (vendor.naics_codes or [])])
                    | Q(description__icontains=vendor.name)
                ).order_by("-posted_date")[:8], many=True
            ).data,
            "contract_vehicles": AwardSerializer(
                awards.filter(award_type__icontains="idv").order_by("-potential_amount")[:8], many=True
            ).data,
            "contacts": list(Contact.objects.filter(vendor_name__iexact=vendor.name).values("id","full_name","title","email","phone")[:10]),
        })
    return Response({"total_records": len(results), "results": results})


@api_view(["GET"])
def partner_discovery(request):
    query = str(request.query_params.get("q") or "").strip()
    naics = str(request.query_params.get("naics") or "").strip()
    state_code = str(request.query_params.get("state") or "").strip()
    socioeconomic = str(request.query_params.get("status") or "").strip()

    vendors = Vendor.objects.all()
    if query:
        vendors = vendors.filter(Q(name__icontains=query) | Q(uei__icontains=query) | Q(cage_code__icontains=query))
    if state_code:
        vendors = vendors.filter(state__iexact=state_code)
    # JSON containment behavior varies by database backend, so list filters are
    # applied in Python after the portable name/state query.
    candidates = list(vendors.order_by("-obligated_amount", "-award_count", "name")[:500])
    if naics:
        candidates = [vendor for vendor in candidates if naics in [str(code) for code in (vendor.naics_codes or [])] or naics.lower() in str(vendor.raw_data).lower()]
    if socioeconomic:
        term = socioeconomic.lower()
        candidates = [vendor for vendor in candidates if any(term in str(item).lower() for item in (vendor.socioeconomic_statuses or [])) or term in str(vendor.raw_data).lower()]

    results = []
    for vendor in candidates[:100]:
        awards = Award.objects.filter(recipient_name=vendor.name)
        top_agencies = list(
            awards.exclude(awarding_agency="")
            .values("awarding_agency")
            .annotate(obligated=Sum("obligated_amount"), awards=Count("id"))
            .order_by("-obligated")[:3]
        )
        results.append({
            "id": vendor.id,
            "name": vendor.name,
            "uei": vendor.uei,
            "cage_code": vendor.cage_code,
            "city": vendor.city,
            "state": vendor.state,
            "website": vendor.website,
            "socioeconomic_statuses": vendor.socioeconomic_statuses,
            "naics_codes": vendor.naics_codes,
            "award_count": awards.count() or vendor.award_count,
            "obligated_amount": awards.aggregate(total=Sum("obligated_amount"))["total"] or vendor.obligated_amount,
            "top_agencies": top_agencies,
        })
    return Response({"total_records": len(results), "results": results})


@api_view(["GET"])
def category_market_intelligence(request):
    category_type = str(request.query_params.get("type") or "naics").lower()
    if category_type not in {"naics", "psc"}:
        return Response({"detail": "type must be naics or psc."}, status=status.HTTP_400_BAD_REQUEST)
    code_field = "naics_code" if category_type == "naics" else "psc_code"
    award_rows = list(
        Award.objects.exclude(**{code_field: ""})
        .values(code_field)
        .annotate(obligated=Sum("obligated_amount"), award_count=Count("id"), vendor_count=Count("recipient_name", distinct=True), agency_count=Count("awarding_agency", distinct=True))
        .order_by("-obligated")[:100]
    )
    opportunity_counts = {
        row[code_field]: row["opportunity_count"]
        for row in Opportunity.objects.exclude(**{code_field: ""}).values(code_field).annotate(opportunity_count=Count("id"))
    }
    results = []
    for row in award_rows:
        code = row.pop(code_field)
        results.append({"code": code, **row, "opportunity_count": opportunity_counts.get(code, 0)})
    return Response({"category_type": category_type, "total_records": len(results), "results": results})


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def run_saved_search_alerts(request):
    from .tasks import evaluate_saved_search_alerts
    try:
        organization = _request_organization(request)
    except Organization.DoesNotExist:
        return Response({"detail": "A valid workspace membership is required."}, status=status.HTTP_403_FORBIDDEN)
    result = evaluate_saved_search_alerts.run(organization_id=organization.id)
    return Response(result)


class IntelligenceAlertViewSet(OrganizationScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = IntelligenceAlertSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = self.scope_queryset(
            IntelligenceAlert.objects.select_related("organization", "saved_search", "opportunity")
        )
        read = self.request.query_params.get("read")
        dismissed = self.request.query_params.get("dismissed")
        if read is not None:
            queryset = queryset.filter(read=_truthy(read))
        if dismissed is not None:
            queryset = queryset.filter(dismissed=_truthy(dismissed))
        return queryset


class ProjectRoomViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectRoomSerializer
    permission_classes = [ReadOnlyOrContributor]

    def get_queryset(self):
        organization = _request_organization(self.request)
        return ProjectRoom.objects.filter(deleted_at__isnull=True).filter(Q(owner_organization=organization) | Q(partners__organization=organization)).select_related("owner_organization", "opportunity", "created_by").prefetch_related("partners__organization").distinct()

    def perform_create(self, serializer):
        serializer.save(owner_organization=_request_organization(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        room = self.get_object()
        if room.owner_organization_id != _request_organization(self.request).id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the owning company can modify this Project Room.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner_organization_id != _request_organization(self.request).id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the owning company can delete this Project Room.")
        instance.deleted_at = timezone.now()
        instance.status = ProjectRoom.Status.CLOSED
        instance.save(update_fields=["deleted_at", "status", "updated_at"])


@api_view(["POST", "DELETE"])
def project_room_partner(request, room_id: int):
    organization = _request_organization(request)
    room = ProjectRoom.objects.filter(pk=room_id, owner_organization=organization).first()
    if not room:
        return Response({"detail": "Only the owning company can manage Project Room partners."}, status=status.HTTP_403_FORBIDDEN)
    partner_org_id = request.data.get("organization")
    if not partner_org_id:
        return Response({"detail": "Partner organization is required."}, status=status.HTTP_400_BAD_REQUEST)
    partner_org = Organization.objects.filter(pk=partner_org_id).exclude(pk=organization.pk).first()
    if not partner_org:
        return Response({"detail": "Partner organization not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        ProjectRoomPartner.objects.filter(project_room=room, organization=partner_org).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    partner, _ = ProjectRoomPartner.objects.update_or_create(
        project_room=room, organization=partner_org,
        defaults={
            "access_level": request.data.get("access_level", ProjectRoomPartner.AccessLevel.PARTNER),
            "can_upload": bool(request.data.get("can_upload", True)),
            "can_comment": bool(request.data.get("can_comment", True)),
            "can_view_pricing": bool(request.data.get("can_view_pricing", False)),
            "invited_by": request.user,
        },
    )
    return Response(ProjectRoomPartnerSerializer(partner).data, status=status.HTTP_201_CREATED)


class AIConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIConversationSerializer
    permission_classes = [ReadOnlyOrContributor]

    def get_queryset(self):
        organization = _request_organization(self.request)
        shared_rooms = ProjectRoom.objects.filter(partners__organization=organization)
        return AIConversation.objects.filter(Q(organization=organization) | Q(project_room__in=shared_rooms, visibility=AIConversation.Visibility.SHARED)).select_related("project_room", "opportunity", "created_by").prefetch_related("messages").distinct()

ANALYSIS_PROMPTS = {
    "executive_summary": "Create an executive opportunity briefing. Cover buyer, scope, key dates, place of performance, contract vehicle/type if stated, set-aside, evaluation approach, mandatory deliverables, major unknowns, and immediate next actions.",
    "requirements": "Extract explicit requirements into categorized bullets. Separate submission instructions, technical requirements, staffing, past performance, certifications, security, insurance, deliverables, and deadlines. Do not infer unstated requirements.",
    "risks": "Identify capture, compliance, technical, staffing, schedule, pricing, security, and teaming risks. Separate confirmed risks from assumptions and recommend mitigations.",
    "bid_no_bid": "Prepare a transparent bid/no-bid brief. State verified facts, unknowns, strengths, gaps, likely teaming needs, resource burden, disqualifiers, and a recommendation. Do not invent a win probability.",
    "compliance_matrix": "Create a compliance matrix in markdown with columns Requirement, Source, Response Owner, Status, and Notes. Include only requirements supported by the provided documents.",
    "amendment_comparison": "Compare the ingested documents as potential versions or amendments. Identify changed dates, scope, clauses, attachments, instructions, and evaluation language. If versions cannot be reliably matched, say so clearly.",
    "sections_l_m": "Locate and summarize Section L / instructions to offerors and Section M / evaluation factors. Cite the exact source passages. If either section is not present, say so.",
    "clin_deliverables": "Extract CLINs, SUBCLINs, ELINs, CDRLs, deliverables, quantities, units, and stated delivery schedules. Do not invent missing line items.",
    "security_compliance": "Extract explicit FAR, DFARS, CMMC, NIST, cybersecurity, insurance, certification, and security requirements. Separate mandatory requirements from references or background.",
}

def _opportunity_for_source(source_id: str):
    return Opportunity.objects.filter(Q(source_id=source_id) | Q(solicitation_number=source_id)).order_by("-updated_at").first()

def _document_context(organization, opportunity, *, query: str = "", limit: int = 18):
    chunks = list(OpportunityDocumentChunk.objects.filter(document__organization=organization, document__opportunity=opportunity, document__status=OpportunityDocument.Status.READY).select_related("document").order_by("document__file_name", "ordinal"))
    terms = [term.lower() for term in query.split() if len(term) > 3][:12]
    if terms:
        chunks.sort(key=lambda chunk: sum(chunk.text.lower().count(term) for term in terms), reverse=True)
    selected = chunks[:limit]
    lines, sources = [], []
    for index, chunk in enumerate(selected, 1):
        label = f"[DOC-{index}]"
        location = f"page {chunk.page_number}" if chunk.page_number else (chunk.section or "extracted text")
        lines.append(f"{label} {chunk.document.file_name} — {location}\n{chunk.text}")
        sources.append({"label": label, "type": "document", "title": f"{chunk.document.file_name} — {location}", "url": chunk.document.source_url})
    return "\n\n".join(lines), sources

@api_view(["GET", "POST"])
def opportunity_documents(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if request.method == "GET" and not opportunity:
        return Response([])
    if not opportunity:
        opportunity_data = request.data.get("opportunity") or {}
        opportunity = Opportunity.objects.create(
            source="sam.gov", source_id=source_id,
            solicitation_number=str(opportunity_data.get("solicitationNumber") or source_id)[:120],
            title=str(opportunity_data.get("title") or f"SAM.gov opportunity {source_id}")[:500],
            agency=str(opportunity_data.get("fullParentPathName") or "")[:255],
            naics_code=str(opportunity_data.get("naicsCode") or "")[:12],
            source_url=str(opportunity_data.get("uiLink") or ""),
            raw_data=opportunity_data if isinstance(opportunity_data, dict) else {},
        )
    if request.method == "GET":
        records = OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).prefetch_related("chunks")
        return Response(OpportunityDocumentSerializer(records, many=True).data)
    documents = request.data.get("documents") or []
    if not isinstance(documents, list) or not documents:
        return Response({"detail": "documents must be a non-empty list of {name, url} records."}, status=status.HTTP_400_BAD_REQUEST)
    results = []
    for row in documents[:40]:
        name = _clean_attachment_name((row or {}).get("name"), (row or {}).get("url"), fallback="Government document")
        url = str((row or {}).get("url") or "").strip()
        if not url:
            continue
        record, _ = OpportunityDocument.objects.update_or_create(organization=organization, opportunity=opportunity, source_url=url, defaults={"file_name": name, "status": OpportunityDocument.Status.PENDING, "error_message": ""})
        try:
            data, content_type = download_document(url)
            digest = sha256(data)
            if record.checksum != digest or record.status != OpportunityDocument.Status.READY:
                sections = extract_document(data, name, content_type)
                if not sections:
                    raise DocumentIngestionError("No readable text could be extracted from this document.")
                OpportunityDocumentChunk.objects.filter(document=record).delete()
                chunk_rows = [OpportunityDocumentChunk(document=record, ordinal=ordinal, page_number=page, section=section or "", text=text) for page, section, ordinal, text in chunk_sections(sections)]
                OpportunityDocumentChunk.objects.bulk_create(chunk_rows, batch_size=250)
                record.content_type = content_type
                record.checksum = digest
                record.status = OpportunityDocument.Status.READY
                record.page_count = len({page for page, _, _ in sections if page})
                record.character_count = sum(len(text) for _, _, text in sections)
                record.error_message = ""
                metadata = dict(record.metadata or {})
                metadata["structured_intelligence"] = extract_structured_intelligence(sections)
                metadata["ingestion"] = {
                    "checksum": digest,
                    "content_type": content_type,
                    "indexed_at": timezone.now().isoformat(),
                }
                record.metadata = metadata
                record.save()
        except (DocumentIngestionError, ValueError, OSError) as exc:
            record.status = OpportunityDocument.Status.FAILED
            record.error_message = str(exc)[:1000]
            record.save(update_fields=["status", "error_message", "updated_at"])
        results.append(record)
    return Response(OpportunityDocumentSerializer(results, many=True).data, status=status.HTTP_201_CREATED)

def _opportunity_context(opportunity):
    raw = opportunity.raw_data if isinstance(opportunity.raw_data, dict) else {}
    fields = [
        ("[OPP-1]", "Title", opportunity.title),
        ("[OPP-2]", "Solicitation", opportunity.solicitation_number),
        ("[OPP-3]", "Agency", opportunity.agency),
        ("[OPP-4]", "Office", opportunity.office),
        ("[OPP-5]", "Description", opportunity.description or raw.get("description")),
        ("[OPP-6]", "NAICS", opportunity.naics_code),
        ("[OPP-7]", "PSC", opportunity.psc_code),
        ("[OPP-8]", "Set-aside", opportunity.set_aside),
        ("[OPP-9]", "Place of performance", opportunity.place_of_performance),
        ("[OPP-10]", "Response deadline", opportunity.response_deadline.isoformat() if opportunity.response_deadline else ""),
        ("[OPP-11]", "Notice type", opportunity.notice_type_raw or opportunity.notice_type),
    ]
    lines=[]; sources=[]
    for label, title, value in fields:
        if value:
            lines.append(f"{label} {title}: {value}")
            sources.append({"label":label,"type":"opportunity","title":title,"url":opportunity.source_url})
    return "\n".join(lines), sources


@api_view(["GET", "POST"])
@throttle_classes([OpenAIChatThrottle])
def opportunity_briefing(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if request.method == "GET" and not opportunity:
        return Response({"documents": [], "analyses": []})
    if not opportunity:
        return Response({"detail": "Ingest the opportunity documents before generating a briefing."}, status=status.HTTP_409_CONFLICT)
    if request.method == "GET":
        analyses = OpportunityAnalysis.objects.filter(organization=organization, opportunity=opportunity)
        documents = OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity).prefetch_related("chunks")
        document_rows = list(documents)
        return Response({
            "documents": OpportunityDocumentSerializer(document_rows, many=True).data,
            "analyses": OpportunityAnalysisSerializer(analyses, many=True).data,
            "capture_readiness": capture_readiness_summary(document_rows),
            "structured_intelligence": [
                {
                    "document_id": document.id,
                    "file_name": document.file_name,
                    **((document.metadata or {}).get("structured_intelligence") or {}),
                }
                for document in document_rows
                if document.status == OpportunityDocument.Status.READY
            ],
        })
    analysis_type = str(request.data.get("analysis_type") or "executive_summary")
    if analysis_type not in ANALYSIS_PROMPTS:
        return Response({"detail": "Unsupported analysis type."}, status=status.HTTP_400_BAD_REQUEST)
    document_context, document_sources = _document_context(organization, opportunity, query=ANALYSIS_PROMPTS[analysis_type], limit=24)
    opportunity_context, opportunity_sources = _opportunity_context(opportunity)
    context = "\n\n".join(part for part in (opportunity_context, document_context) if part)
    sources = opportunity_sources + document_sources
    fingerprint_source = analysis_type + "|" + str(opportunity.updated_at.timestamp()) + "|" + "|".join(sorted(doc.checksum for doc in OpportunityDocument.objects.filter(organization=organization, opportunity=opportunity, status=OpportunityDocument.Status.READY)))
    fingerprint = sha256(fingerprint_source.encode())
    cached = OpportunityAnalysis.objects.filter(organization=organization, opportunity=opportunity, project_room=None, analysis_type=analysis_type, input_fingerprint=fingerprint).first()
    if cached and not request.data.get("refresh"):
        return Response(OpportunityAnalysisSerializer(cached).data)
    prompt = f"Opportunity: {opportunity.title}\nSolicitation: {opportunity.solicitation_number}\nAgency: {opportunity.agency}\n\nTASK\n{ANALYSIS_PROMPTS[analysis_type]}\n\nAUTHORIZED OPPORTUNITY AND DOCUMENT CONTEXT\n{context}\n\nCite every document-supported claim using the exact [DOC-*] labels. Clearly label unknowns and inferences."
    result = ask_ai(message=prompt, history=[], organization=organization)
    analysis, _ = OpportunityAnalysis.objects.update_or_create(organization=organization, opportunity=opportunity, project_room=None, analysis_type=analysis_type, input_fingerprint=fingerprint, defaults={"content": result.get("answer", ""), "sources": sources, "model": result.get("model", ""), "created_by": request.user})
    return Response(OpportunityAnalysisSerializer(analysis).data)

@api_view(["POST"])
@throttle_classes([OpenAIChatThrottle])
def opportunity_document_question(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    question = str(request.data.get("message") or "").strip()
    if not opportunity:
        return Response({"detail": "Opportunity not found."}, status=status.HTTP_404_NOT_FOUND)
    if not question:
        return Response({"detail": "A question is required."}, status=status.HTTP_400_BAD_REQUEST)
    document_context, document_sources = _document_context(organization, opportunity, query=question, limit=18)
    opportunity_context, opportunity_sources = _opportunity_context(opportunity)
    context = "\n\n".join(part for part in (opportunity_context, document_context) if part)
    sources = opportunity_sources + document_sources
    mode = "opportunity details plus ingested documents" if document_context else "opportunity details only"
    result = ask_ai(message=f"Respond like an experienced capture manager speaking to a colleague. Lead with the direct answer, use short readable paragraphs, and avoid dumping raw fields. Use only the authorized {mode}. Cite exact [OPP-*] and [DOC-*] labels for factual claims. If the available context cannot answer something, say exactly what is missing.\n\nQUESTION\n{question}\n\nAUTHORIZED CONTEXT\n{context}", history=[], organization=organization)
    result["sources"] = sources
    return Response(result)


@api_view(["GET"])
def opportunity_document_intelligence(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if not opportunity:
        return Response({"detail": "Opportunity not found."}, status=status.HTTP_404_NOT_FOUND)
    documents = list(
        OpportunityDocument.objects.filter(
            organization=organization,
            opportunity=opportunity,
        ).prefetch_related("chunks")
    )
    return Response({
        "opportunity": {
            "source_id": opportunity.source_id,
            "title": opportunity.title,
            "solicitation_number": opportunity.solicitation_number,
        },
        "capture_readiness": capture_readiness_summary(documents),
        "documents": [
            {
                "id": document.id,
                "file_name": document.file_name,
                "status": document.status,
                "source_url": document.source_url,
                "page_count": document.page_count,
                "character_count": document.character_count,
                "structured_intelligence": (document.metadata or {}).get("structured_intelligence") or {},
                "error_message": document.error_message,
            }
            for document in documents
        ],
    })


@api_view(["GET", "POST"])
@throttle_classes([OpenAIChatThrottle])
def opportunity_capture_assessment(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if not opportunity:
        return Response({"detail": "Opportunity not found."}, status=status.HTTP_404_NOT_FOUND)
    include_ai = request.method == "POST" or _truthy(request.query_params.get("include_ai"))
    refresh_ai = request.method == "POST" and _truthy(str(request.data.get("refresh", "false")))
    payload = build_capture_assessment(
        organization=organization,
        opportunity=opportunity,
        include_ai=include_ai,
        refresh_ai=refresh_ai,
        user=request.user,
    )
    return Response(payload)


@api_view(["GET"])
def opportunity_win_strategy(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if not opportunity:
        return Response({"detail": "Opportunity not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(build_win_strategy(organization=organization, opportunity=opportunity))


@api_view(["GET"])
def opportunity_capture_command_center(request, source_id: str):
    organization = _request_organization(request)
    opportunity = _opportunity_for_source(source_id)
    if not opportunity:
        return Response({"detail": "Opportunity not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(build_capture_command_center(organization=organization, opportunity=opportunity))


def _room_access(request, room_id):
    organization = _request_organization(request)
    room = ProjectRoom.objects.filter(Q(owner_organization=organization) | Q(partners__organization=organization), pk=room_id).select_related("owner_organization").distinct().first()
    if not room:
        return None, None, False
    owner = room.owner_organization_id == organization.id
    partner = None if owner else ProjectRoomPartner.objects.filter(project_room=room, organization=organization).first()
    return room, partner, owner

def _visible_room_queryset(queryset, room, owner):
    return queryset if owner else queryset.filter(visibility="shared")

def _log_room_activity(room, actor, action, summary, *, visibility="shared", object_type="", object_id="", metadata=None):
    return ProjectRoomActivity.objects.create(project_room=room, actor=actor, action=action, summary=summary, visibility=visibility, object_type=object_type, object_id=str(object_id or ""), metadata=metadata or {})


@api_view(["GET", "POST", "PATCH", "DELETE"])
def project_room_access_management(request, room_id):
    room, partner, owner = _room_access(request, room_id)
    if not room:
        return Response({"detail": "Project Room not found."}, status=404)
    organization = _request_organization(request)
    if request.method == "GET":
        internal_members = ProjectRoomMember.objects.filter(project_room=room).select_related("membership__user", "membership") if owner else ProjectRoomMember.objects.none()
        partners = ProjectRoomPartner.objects.filter(project_room=room).select_related("organization")
        available_members = Membership.objects.filter(organization=organization).select_related("user") if owner else Membership.objects.none()
        return Response({
            "owner": owner,
            "owner_organization": room.owner_organization_id,
            "members": ProjectRoomMemberSerializer(internal_members, many=True).data,
            "available_members": MembershipSerializer(available_members, many=True).data,
            "partners": ProjectRoomPartnerSerializer(partners, many=True).data,
        })
    if not owner:
        return Response({"detail": "Only the owning company can manage room access."}, status=403)
    kind = str(request.data.get("kind") or "member")
    if kind == "member":
        membership_id = request.query_params.get("membership") if request.method == "DELETE" else request.data.get("membership")
        membership = Membership.objects.filter(pk=membership_id, organization=organization).first()
        if not membership:
            return Response({"detail": "Workspace member not found."}, status=404)
        if request.method == "DELETE":
            ProjectRoomMember.objects.filter(project_room=room, membership=membership).delete()
            return Response(status=204)
        row, _ = ProjectRoomMember.objects.update_or_create(project_room=room, membership=membership, defaults={"role": request.data.get("role", "contributor"), "added_by": request.user})
        return Response(ProjectRoomMemberSerializer(row).data, status=201)
    partner_org_id = request.query_params.get("organization") if request.method == "DELETE" else request.data.get("organization")
    partner_row = ProjectRoomPartner.objects.filter(project_room=room, organization_id=partner_org_id).first()
    if not partner_row:
        return Response({"detail": "Partner company is not in this room."}, status=404)
    if request.method == "DELETE":
        partner_row.delete()
        return Response(status=204)
    serializer = ProjectRoomPartnerSerializer(partner_row, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    return Response(ProjectRoomPartnerSerializer(serializer.save()).data)

@api_view(["GET", "POST"])
def project_room_tasks(request, room_id):
    room, partner, owner = _room_access(request, room_id)
    if not room: return Response({"detail":"Project Room not found."}, status=404)
    if request.method == "GET":
        qs=_visible_room_queryset(ProjectRoomTask.objects.filter(project_room=room).select_related("assigned_to","created_by"), room, owner)
        return Response(ProjectRoomTaskSerializer(qs, many=True).data)
    visibility=request.data.get("visibility","shared")
    if visibility=="internal" and not owner: return Response({"detail":"Partner companies cannot create internal tasks."}, status=403)
    serializer=ProjectRoomTaskSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    task=serializer.save(project_room=room, created_by=request.user)
    _log_room_activity(room,request.user,"task_created",f"Created task: {task.title}",visibility=visibility,object_type="task",object_id=task.id)
    return Response(ProjectRoomTaskSerializer(task).data,status=201)

@api_view(["PATCH", "DELETE"])
def project_room_task_detail(request, room_id, task_id):
    room, partner, owner=_room_access(request,room_id)
    if not room: return Response({"detail":"Project Room not found."},status=404)
    task=ProjectRoomTask.objects.filter(project_room=room,pk=task_id).first()
    if not task or (not owner and task.visibility!="shared"): return Response({"detail":"Task not found."},status=404)
    if request.method=="DELETE":
        if not owner and task.created_by_id!=request.user.id: return Response({"detail":"Only the owner company or task creator can delete this task."},status=403)
        task.delete(); return Response(status=204)
    serializer=ProjectRoomTaskSerializer(task,data=request.data,partial=True); serializer.is_valid(raise_exception=True); task=serializer.save()
    _log_room_activity(room,request.user,"task_updated",f"Updated task: {task.title}",visibility=task.visibility,object_type="task",object_id=task.id)
    return Response(ProjectRoomTaskSerializer(task).data)

@api_view(["GET", "POST"])
def project_room_comments(request, room_id):
    room, partner, owner=_room_access(request,room_id)
    if not room: return Response({"detail":"Project Room not found."},status=404)
    if request.method=="GET":
        qs=_visible_room_queryset(ProjectRoomComment.objects.filter(project_room=room).select_related("author"),room,owner)
        return Response(ProjectRoomCommentSerializer(qs,many=True).data)
    if partner and not partner.can_comment: return Response({"detail":"This company cannot comment in this room."},status=403)
    visibility=request.data.get("visibility","shared")
    if visibility=="internal" and not owner: return Response({"detail":"Partner companies cannot create internal comments."},status=403)
    serializer=ProjectRoomCommentSerializer(data=request.data); serializer.is_valid(raise_exception=True); comment=serializer.save(project_room=room,author=request.user)
    _log_room_activity(room,request.user,"comment_added","Added a project comment",visibility=visibility,object_type="comment",object_id=comment.id)
    return Response(ProjectRoomCommentSerializer(comment).data,status=201)

@api_view(["GET", "POST"])
def project_room_notes(request, room_id):
    room, partner, owner=_room_access(request,room_id)
    if not room: return Response({"detail":"Project Room not found."},status=404)
    if request.method=="GET":
        qs=_visible_room_queryset(ProjectRoomNote.objects.filter(project_room=room).select_related("author"),room,owner)
        return Response(ProjectRoomNoteSerializer(qs,many=True).data)
    visibility=request.data.get("visibility","internal")
    if visibility=="internal" and not owner: return Response({"detail":"Partner companies cannot create internal notes."},status=403)
    serializer=ProjectRoomNoteSerializer(data=request.data); serializer.is_valid(raise_exception=True); note=serializer.save(project_room=room,author=request.user)
    _log_room_activity(room,request.user,"note_created",f"Created note: {note.title}",visibility=visibility,object_type="note",object_id=note.id)
    return Response(ProjectRoomNoteSerializer(note).data,status=201)

@api_view(["GET", "POST"])
def project_room_files(request, room_id):
    room, partner, owner=_room_access(request,room_id)
    if not room: return Response({"detail":"Project Room not found."},status=404)
    if request.method=="GET":
        qs=ProjectRoomFile.objects.filter(project_room=room).select_related("uploaded_by")
        if not owner:
            allowed=["shared"] + (["pricing"] if partner and partner.can_view_pricing else [])
            qs=qs.filter(visibility__in=allowed)
        return Response(ProjectRoomFileSerializer(qs,many=True).data)
    if partner and not partner.can_upload: return Response({"detail":"This company cannot add files to this room."},status=403)
    visibility=request.data.get("visibility","shared")
    if visibility in {"internal","pricing"} and not owner: return Response({"detail":"Only the owner company can create restricted files."},status=403)
    serializer=ProjectRoomFileSerializer(data=request.data); serializer.is_valid(raise_exception=True); file=serializer.save(project_room=room,uploaded_by=request.user)
    _log_room_activity(room,request.user,"file_added",f"Added file: {file.name}",visibility="internal" if visibility=="pricing" else visibility,object_type="file",object_id=file.id)
    return Response(ProjectRoomFileSerializer(file).data,status=201)

@api_view(["GET"])
def project_room_activity(request, room_id):
    room, partner, owner=_room_access(request,room_id)
    if not room: return Response({"detail":"Project Room not found."},status=404)
    qs=_visible_room_queryset(ProjectRoomActivity.objects.filter(project_room=room).select_related("actor"),room,owner)[:200]
    return Response(ProjectRoomActivitySerializer(qs,many=True).data)

class CollaborationNotificationViewSet(viewsets.ModelViewSet):
    serializer_class=CollaborationNotificationSerializer
    http_method_names=["get","patch","head","options"]
    def get_queryset(self):
        organization = _request_organization(self.request)
        return CollaborationNotification.objects.filter(
            Q(user=self.request.user) | Q(organization=organization, user__isnull=True)
        ).select_related("organization", "project_room")


def _network_connection_between(left, right):
    return NetworkConnection.objects.filter(Q(requester=left, recipient=right) | Q(requester=right, recipient=left)).order_by("-updated_at").first()


@api_view(["GET"])
def network_directory(request):
    organization = _request_organization(request)
    query = str(request.query_params.get("q") or "").strip()
    certification = str(request.query_params.get("certification") or "").strip()
    state_filter = str(request.query_params.get("state") or "").strip()
    profiles = OrganizationProfile.objects.select_related("organization").filter(is_public=True).exclude(organization=organization)
    if query:
        profiles = profiles.filter(Q(organization__name__icontains=query) | Q(tagline__icontains=query) | Q(description__icontains=query) | Q(capabilities__icontains=query) | Q(organization__cage_code__icontains=query) | Q(organization__uei__icontains=query))
    if certification:
        profiles = profiles.filter(certifications__icontains=certification)
    if state_filter:
        profiles = profiles.filter(state__iexact=state_filter)
    data = OrganizationProfileSerializer(profiles[:100], many=True).data
    for row in data:
        connection = _network_connection_between(organization, Organization.objects.get(pk=row["organization_id"]))
        row["connection_status"] = connection.status if connection else "none"
        row["connection_id"] = connection.id if connection else None
    return Response({"results": data, "count": len(data)})


@api_view(["GET", "PATCH"])
@permission_classes([ReadOnlyOrContributor])
def network_profile(request):
    organization = _request_organization(request)
    profile, _ = OrganizationProfile.objects.get_or_create(organization=organization)
    if request.method == "PATCH":
        membership = active_membership(request.user)
        if not membership or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
            return Response({"detail": "Only company owners and administrators can edit the company profile."}, status=status.HTTP_403_FORBIDDEN)
        for field in ("name", "uei", "cage_code"):
            if field in request.data:
                setattr(organization, field, str(request.data.get(field) or "").strip())
        organization.save(update_fields=["name", "uei", "cage_code", "updated_at"])
        serializer = OrganizationProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrganizationProfileSerializer(profile).data)
    return Response(OrganizationProfileSerializer(profile).data)


@api_view(["GET", "POST"])
@permission_classes([ReadOnlyOrContributor])
def network_connections(request):
    organization = _request_organization(request)
    if request.method == "GET":
        rows = NetworkConnection.objects.filter(Q(requester=organization) | Q(recipient=organization)).select_related("requester", "recipient")
        status_filter = str(request.query_params.get("status") or "").strip()
        if status_filter:
            rows = rows.filter(status=status_filter)
        return Response(NetworkConnectionSerializer(rows, many=True).data)
    recipient_id = request.data.get("recipient")
    recipient = Organization.objects.filter(pk=recipient_id).exclude(pk=organization.pk).first()
    if not recipient:
        return Response({"detail": "Company not found."}, status=status.HTTP_404_NOT_FOUND)
    existing = _network_connection_between(organization, recipient)
    if existing and existing.status in {NetworkConnection.Status.PENDING, NetworkConnection.Status.ACCEPTED}:
        return Response(NetworkConnectionSerializer(existing).data, status=status.HTTP_200_OK)
    row = NetworkConnection.objects.create(requester=organization, recipient=recipient, requested_by=request.user, message=str(request.data.get("message") or "")[:2000])
    notify_organization_members(organization=recipient, title=f"Connection request from {organization.name}", message=row.message or "A company wants to connect with your team.", kind="network_connection", link="/network?tab=invitations")
    return Response(NetworkConnectionSerializer(row).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def network_connection_response(request, connection_id: int):
    organization = _request_organization(request)
    row = NetworkConnection.objects.filter(pk=connection_id, recipient=organization, status=NetworkConnection.Status.PENDING).select_related("requester", "recipient").first()
    if not row:
        return Response({"detail": "Pending invitation not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action not in {"accept", "decline"}:
        return Response({"detail": "action must be accept or decline."}, status=status.HTTP_400_BAD_REQUEST)
    row.status = NetworkConnection.Status.ACCEPTED if action == "accept" else NetworkConnection.Status.DECLINED
    row.responded_by = request.user
    row.responded_at = timezone.now()
    row.save(update_fields=["status", "responded_by", "responded_at", "updated_at"])
    notify_organization_members(organization=row.requester, title=f"Connection request {action}ed", message=f"{organization.name} {action}ed your company connection request.", kind="network_connection_response", link="/network?tab=partners")
    return Response(NetworkConnectionSerializer(row).data)




@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def network_connection_manage(request, connection_id: int):
    organization = _request_organization(request)
    row = NetworkConnection.objects.filter(pk=connection_id).filter(Q(requester=organization)|Q(recipient=organization)).select_related("requester","recipient").first()
    if not row:
        return Response({"detail":"Connection not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action == "cancel" and row.requester_id == organization.id and row.status == NetworkConnection.Status.PENDING:
        row.status = NetworkConnection.Status.CANCELLED
    elif action == "disconnect" and row.status == NetworkConnection.Status.ACCEPTED:
        row.status = NetworkConnection.Status.DISCONNECTED
        ProjectRoomPartner.objects.filter(organization=organization).delete()
    elif action == "block" and row.recipient_id == organization.id:
        row.status = NetworkConnection.Status.BLOCKED
    elif action == "unblock" and row.status == NetworkConnection.Status.BLOCKED:
        row.status = NetworkConnection.Status.DISCONNECTED
    else:
        return Response({"detail":"That action is not valid for the current relationship state."}, status=status.HTTP_400_BAD_REQUEST)
    row.responded_by=request.user; row.responded_at=timezone.now(); row.save(update_fields=["status","responded_by","responded_at","updated_at"])
    other = row.recipient if row.requester_id == organization.id else row.requester
    notify_organization_members(organization=other,title=f"Partnership {row.status}",message=f"{organization.name} changed the company relationship to {row.status}.",kind="network_connection_update",link="/network?tab=partners")
    return Response(NetworkConnectionSerializer(row).data)


@api_view(["GET"])
def naics_catalog(request):
    import json
    from pathlib import Path
    rows=json.loads((Path(__file__).resolve().parent/"data"/"naics_2022.json").read_text())
    q=str(request.query_params.get("q") or "").strip().lower()
    if q:
        rows=[r for r in rows if q in r["code"].lower() or q in r["title"].lower()]
    level=request.query_params.get("level")
    if level and str(level).isdigit(): rows=[r for r in rows if r["level"]==int(level)]
    return Response({"version":"2022","source":"U.S. Census Bureau","results":rows[:250]})


@api_view(["GET", "POST"])
@permission_classes([ReadOnlyOrContributor])
def project_room_invitations(request):
    organization = _request_organization(request)
    if request.method == "GET":
        rows = ProjectRoomInvitation.objects.filter(Q(invited_organization=organization) | Q(project_room__owner_organization=organization)).select_related("project_room", "project_room__owner_organization", "invited_organization")
        return Response(ProjectRoomInvitationSerializer(rows, many=True).data)
    room = ProjectRoom.objects.filter(pk=request.data.get("project_room"), owner_organization=organization).first()
    invited_org = Organization.objects.filter(pk=request.data.get("invited_organization")).exclude(pk=organization.pk).first()
    if not room or not invited_org:
        return Response({"detail": "Valid owned Project Room and partner company are required."}, status=status.HTTP_400_BAD_REQUEST)
    connection = _network_connection_between(organization, invited_org)
    if not connection or connection.status != NetworkConnection.Status.ACCEPTED:
        return Response({"detail": "Connect with this company before inviting it to a Project Room."}, status=status.HTTP_403_FORBIDDEN)
    row, created = ProjectRoomInvitation.objects.update_or_create(project_room=room, invited_organization=invited_org, status=ProjectRoomInvitation.Status.PENDING, defaults={"invited_by": request.user, "access_level": request.data.get("access_level", ProjectRoomPartner.AccessLevel.PARTNER), "can_upload": bool(request.data.get("can_upload", True)), "can_comment": bool(request.data.get("can_comment", True)), "can_view_pricing": bool(request.data.get("can_view_pricing", False)), "message": str(request.data.get("message") or "")[:2000], "expires_at": timezone.now()+timedelta(days=14), "last_sent_at": timezone.now()})
    link = f"/network?tab=invitations"
    notify_organization_members(organization=invited_org, title=f"Project Room invitation: {room.name}", message=f"{organization.name} invited your company to collaborate.", kind="project_room_invitation", link=link, project_room=room)
    for member in Membership.objects.filter(organization=invited_org, active=True, role__in=[Membership.Role.OWNER, Membership.Role.ADMIN]).select_related("user"):
        send_system_email(subject=f"Project Room invitation from {organization.name}", message=f"Open ForgeGov to review the invitation to {room.name}: {settings.FRONTEND_URL.rstrip('/')}{link}", recipient=member.user.email)
    ProjectRoomActivity.objects.create(project_room=room, actor=request.user, action="partner_invited", summary=f"Invited {invited_org.name} to the Project Room.")
    return Response(ProjectRoomInvitationSerializer(row).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def project_room_invitation_manage(request, invitation_id: int):
    organization = _request_organization(request)
    row = ProjectRoomInvitation.objects.filter(pk=invitation_id, project_room__owner_organization=organization).select_related("project_room", "invited_organization").first()
    if not row:
        return Response({"detail": "Project Room invitation not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action == "cancel":
        if row.status != ProjectRoomInvitation.Status.PENDING:
            return Response({"detail": "Only pending invitations can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = ProjectRoomInvitation.Status.CANCELLED
        row.responded_at = timezone.now()
        row.save(update_fields=["status", "responded_at", "updated_at"])
    elif action == "resend":
        if row.status not in {ProjectRoomInvitation.Status.PENDING, ProjectRoomInvitation.Status.EXPIRED}:
            return Response({"detail": "Only pending or expired invitations can be resent."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = ProjectRoomInvitation.Status.PENDING
        row.expires_at = timezone.now()+timedelta(days=14)
        row.last_sent_at = timezone.now()
        row.resend_count += 1
        row.save(update_fields=["status", "expires_at", "last_sent_at", "resend_count", "updated_at"])
        link = "/network?tab=invitations"
        notify_organization_members(organization=row.invited_organization, title=f"Project Room invitation: {row.project_room.name}", message=f"{organization.name} resent the collaboration invitation.", kind="project_room_invitation", link=link, project_room=row.project_room)
        for member in Membership.objects.filter(organization=row.invited_organization, active=True, role__in=[Membership.Role.OWNER, Membership.Role.ADMIN]).select_related("user"):
            send_system_email(subject=f"Project Room invitation from {organization.name}", message=f"Open ForgeGov to review the invitation: {settings.FRONTEND_URL.rstrip('/')}{link}", recipient=member.user.email)
    else:
        return Response({"detail": "action must be resend or cancel."}, status=status.HTTP_400_BAD_REQUEST)
    ProjectRoomActivity.objects.create(project_room=row.project_room, actor=request.user, action=f"partner_invitation_{action}", summary=f"{action.title()}ed invitation for {row.invited_organization.name}.")
    return Response(ProjectRoomInvitationSerializer(row).data)


@api_view(["POST"])
@permission_classes([ReadOnlyOrContributor])
def project_room_invitation_response(request, invitation_id: int):
    organization = _request_organization(request)
    row = ProjectRoomInvitation.objects.filter(pk=invitation_id, invited_organization=organization, status=ProjectRoomInvitation.Status.PENDING).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).select_related("project_room").first()
    if not row:
        return Response({"detail": "Pending Project Room invitation not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "").lower()
    if action not in {"accept", "decline"}:
        return Response({"detail": "action must be accept or decline."}, status=status.HTTP_400_BAD_REQUEST)
    row.status = ProjectRoomInvitation.Status.ACCEPTED if action == "accept" else ProjectRoomInvitation.Status.DECLINED
    row.responded_by = request.user
    row.responded_at = timezone.now()
    row.save(update_fields=["status", "responded_by", "responded_at", "updated_at"])
    if action == "accept":
        ProjectRoomPartner.objects.update_or_create(project_room=row.project_room, organization=organization, defaults={"access_level": row.access_level, "can_upload": row.can_upload, "can_comment": row.can_comment, "can_view_pricing": row.can_view_pricing, "invited_by": row.invited_by})
    owner_org = row.project_room.owner_organization
    notify_organization_members(organization=owner_org, title=f"Project Room invitation {action}ed", message=f"{organization.name} {action}ed the invitation to {row.project_room.name}.", kind="project_room_invitation_response", link=f"/project-rooms/{row.project_room_id}", project_room=row.project_room)
    ProjectRoomActivity.objects.create(project_room=row.project_room, actor=request.user, action=f"partner_invitation_{action}ed", summary=f"{organization.name} {action}ed the Project Room invitation.")
    return Response(ProjectRoomInvitationSerializer(row).data)


@api_view(["POST"])
def pipeline_project_room(request, pipeline_id: int):
    organization = _request_organization(request)
    item = PipelineItem.objects.select_related("opportunity", "project_room").filter(pk=pipeline_id, organization=organization).first()
    if not item:
        return Response({"detail": "Pipeline item not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "link")
    if action == "create":
        room = ProjectRoom.objects.create(owner_organization=organization, opportunity=item.opportunity, name=str(request.data.get("name") or item.opportunity.title), description=str(request.data.get("description") or f"Teaming workspace for {item.opportunity.title}"), status=ProjectRoom.Status.ACTIVE, created_by=request.user)
        item.project_room = room; item.assigned_team = room.name
        item.save(update_fields=["project_room", "assigned_team", "updated_at"])
        ProjectRoomActivity.objects.create(project_room=room, actor=request.user, action="room.created_from_pipeline", summary=f"Teaming workspace created from pipeline item {item.opportunity.title}.", metadata={"pipeline_id": item.id})
        return Response(PipelineItemSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED)
    if action == "unlink":
        item.project_room = None; item.assigned_team = ""
        item.save(update_fields=["project_room", "assigned_team", "updated_at"])
        return Response(PipelineItemSerializer(item, context={"request": request}).data)
    room = ProjectRoom.objects.filter(pk=request.data.get("project_room"), owner_organization=organization, deleted_at__isnull=True).first()
    if not room:
        return Response({"detail": "Select a valid Project Room owned by this workspace."}, status=status.HTTP_400_BAD_REQUEST)
    if room.opportunity_id and room.opportunity_id != item.opportunity_id:
        return Response({"detail": "That Project Room is linked to a different opportunity."}, status=status.HTTP_409_CONFLICT)
    if not room.opportunity_id:
        room.opportunity = item.opportunity; room.save(update_fields=["opportunity", "updated_at"])
    item.project_room = room; item.assigned_team = room.name
    item.save(update_fields=["project_room", "assigned_team", "updated_at"])
    return Response(PipelineItemSerializer(item, context={"request": request}).data)

@api_view(["POST"])
def project_room_lifecycle(request, room_id: int):
    organization = _request_organization(request)
    room = ProjectRoom.objects.filter(pk=room_id, owner_organization=organization).first()
    if not room:
        return Response({"detail": "Project Room not found."}, status=status.HTTP_404_NOT_FOUND)
    action = str(request.data.get("action") or "archive")
    if action == "restore":
        room.archived_at = None; room.deleted_at = None; room.status = ProjectRoom.Status.ACTIVE
    elif action == "delete":
        room.deleted_at = timezone.now(); room.status = ProjectRoom.Status.CLOSED
        room.pipeline_items.update(project_room=None, assigned_team="")
    else:
        room.archived_at = timezone.now(); room.status = ProjectRoom.Status.CLOSED
    room.save(update_fields=["archived_at", "deleted_at", "status", "updated_at"])
    return Response(ProjectRoomSerializer(room, context={"request": request}).data)

@api_view(["GET", "POST"])
def organization_join_requests(request):
    membership = active_membership(request.user)
    domain = request.user.email.split("@",1)[1].lower() if "@" in request.user.email else ""
    if request.method == "GET":
        rows = OrganizationJoinRequest.objects.filter(organization=membership.organization) if membership and membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN} else OrganizationJoinRequest.objects.filter(user=request.user)
        return Response(OrganizationJoinRequestSerializer(rows, many=True).data)
    org = Organization.objects.filter(pk=request.data.get("organization")).first()
    profile = OrganizationProfile.objects.filter(organization=org, verified=True).first() if org else None
    website_domain = str(getattr(profile, "website", "")).lower().replace("https://", "").replace("http://", "").split("/",1)[0].removeprefix("www.")
    if not org or not profile or not domain or domain != website_domain:
        return Response({"detail": "Your email domain must match a verified company website before requesting access."}, status=status.HTTP_400_BAD_REQUEST)
    row, _ = OrganizationJoinRequest.objects.get_or_create(organization=org, user=request.user, status=OrganizationJoinRequest.Status.PENDING, defaults={"email_domain": domain})
    notify_organization_members(organization=org, title="Company join request", message=f"{request.user.email} requested access to {org.name}.", kind="company_join_request", link="/company", roles=[Membership.Role.OWNER, Membership.Role.ADMIN])
    return Response(OrganizationJoinRequestSerializer(row).data, status=status.HTTP_201_CREATED)

@api_view(["POST"])
def organization_join_request_response(request, request_id: int):
    membership = active_membership(request.user)
    row = OrganizationJoinRequest.objects.select_related("organization", "user").filter(pk=request_id).first()
    if not row or not membership or membership.organization_id != row.organization_id or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN}:
        return Response({"detail": "Only company owners and administrators can review this request."}, status=status.HTTP_403_FORBIDDEN)
    action = str(request.data.get("action") or "decline")
    if action == "approve":
        Membership.objects.update_or_create(organization=row.organization, user=row.user, defaults={"role": row.requested_role, "active": True})
        row.status = OrganizationJoinRequest.Status.APPROVED
    else:
        row.status = OrganizationJoinRequest.Status.DECLINED
    row.reviewed_by = request.user; row.reviewed_at = timezone.now(); row.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    return Response(OrganizationJoinRequestSerializer(row).data)
