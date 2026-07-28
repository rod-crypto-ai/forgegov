from django.conf import settings
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .permissions import ReadOnlyOrContributor, active_membership
from .ai import OpenAIIntegrationError, ask_openai

from .integrations import (
    IntegrationError,
    fetch_grants_opportunity,
    fetch_sam_opportunity_detail,
    search_grants_opportunities,
    search_sam_opportunities,
    search_sam_contract_awards,
    search_sam_subawards,
    search_sba_subnet_opportunities,
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
    Organization,
    Participant,
    PipelineItem,
    Pursuit,
    SavedSearch,
    Task,
    TeamingRequest,
    Vendor,
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
    OrganizationSerializer,
    ParticipantSerializer,
    PipelineItemSerializer,
    PursuitSerializer,
    SavedSearchSerializer,
    TaskSerializer,
    TeamingRequestSerializer,
    VendorSerializer,
)
from .throttles import OpenAIChatThrottle, SamLiveSearchThrottle


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "forgegov-api", "product": "ForgeGov", "version": "1.2.0"})


@api_view(["GET"])
def integration_status(request):
    probe = _truthy(request.query_params.get("probe"))
    latest_sync = DataSyncRun.objects.filter(source="sam.gov").first()
    latest_usa_sync = DataSyncRun.objects.filter(source="usaspending.gov").first()
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
        "expansion": {
            "forecast_directory": "https://www.acquisition.gov/procurement-forecasts",
            "subnet": settings.SBA_SUBNET_URL,
            "sam_subawards_configured": bool(settings.SAM_GOV_API_KEY),
            "stored_contract_vehicles": Award.objects.filter(award_type=Award.AwardType.VEHICLE).count(),
        },
    })


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
        return Response(ask_openai(message=message, history=history, organization=organization))
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
        ))
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


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
            "socioeconomic_statuses": vendor.socioeconomic_statuses,
            "award_count": awards.count(),
            "obligated_amount": awards.aggregate(total=Sum("obligated_amount"))["total"] or 0,
            "top_agencies": top_agencies,
            "top_naics": top_naics,
            "recent_awards": AwardSerializer(awards.order_by("-start_date", "-updated_at")[:10], many=True).data,
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
