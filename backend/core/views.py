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
    search_grants_opportunities,
    search_sam_opportunities,
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
    return Response({"status": "ok", "service": "forgegov-api", "product": "ForgeGov", "version": "1.0.2"})


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
