from django.conf import settings
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .integrations import IntegrationError, search_sam_opportunities, usaspending_status
from .models import DataSyncRun, Opportunity, Organization, PipelineItem, SavedSearch, Task
from .serializers import (
    DataSyncRunSerializer,
    OpportunitySerializer,
    OrganizationSerializer,
    PipelineItemSerializer,
    SavedSearchSerializer,
    TaskSerializer,
)
from .throttles import SamLiveSearchThrottle


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "service": "forgegov-api", "product": "ForgeGov"})


@api_view(["GET"])
def integration_status(request):
    probe = _truthy(request.query_params.get("probe"))
    latest_sync = DataSyncRun.objects.filter(source="sam.gov").first()
    return Response({
        "sam_gov": {
            "configured": bool(settings.SAM_GOV_API_KEY),
            "base_url": settings.SAM_GOV_BASE_URL,
            "latest_sync": DataSyncRunSerializer(latest_sync).data if latest_sync else None,
        },
        "usaspending": usaspending_status(probe=probe),
    })


@api_view(["GET"])
def dashboard_summary(request):
    pipeline_counts = {
        row["stage"]: row["count"]
        for row in PipelineItem.objects.values("stage").annotate(count=Count("id"))
    }
    return Response({
        "opportunities": {
            "total": Opportunity.objects.count(),
            "active": Opportunity.objects.filter(active=True).count(),
        },
        "pipeline": {
            "total": PipelineItem.objects.count(),
            "by_stage": pipeline_counts,
        },
        "tasks": {
            "open": Task.objects.filter(completed=False).count(),
            "completed": Task.objects.filter(completed=True).count(),
        },
        "workspaces": Organization.objects.count(),
        "saved_searches": SavedSearch.objects.filter(enabled=True).count(),
    })


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
    except (IntegrationError, TypeError, ValueError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer


class OpportunityViewSet(viewsets.ModelViewSet):
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


class PipelineItemViewSet(viewsets.ModelViewSet):
    queryset = PipelineItem.objects.select_related("opportunity", "organization", "owner").all()
    serializer_class = PipelineItemSerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("organization", "pipeline_item", "assigned_to").all()
    serializer_class = TaskSerializer


class SavedSearchViewSet(viewsets.ModelViewSet):
    queryset = SavedSearch.objects.select_related("organization", "owner").all()
    serializer_class = SavedSearchSerializer


class DataSyncRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataSyncRun.objects.all()
    serializer_class = DataSyncRunSerializer
