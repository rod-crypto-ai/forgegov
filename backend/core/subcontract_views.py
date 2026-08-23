from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Opportunity
from .permissions import active_membership
from .subcontract_intelligence import build_subcontract_workspace


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subcontract_workspace_detail(request, source_id: str):
    membership = active_membership(request.user)
    if not membership:
        return Response({"detail": "An active ForgeGov company workspace is required."}, status=status.HTTP_403_FORBIDDEN)
    opportunity = Opportunity.objects.filter(source_id=source_id, source="sba-subnet").first()
    if not opportunity:
        return Response({"detail": "This SUBNet opportunity is not indexed in ForgeGov yet. Refresh the Subcontracting page and try again."}, status=status.HTTP_404_NOT_FOUND)
    return Response(build_subcontract_workspace(opportunity=opportunity, organization=membership.organization))
