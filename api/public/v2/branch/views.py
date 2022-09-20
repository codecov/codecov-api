from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins

from api.public.v2.schema import repo_parameters
from api.shared.branch.mixins import BranchViewSetMixin
from core.models import Branch

from .serializers import BranchDetailSerializer, BranchSerializer


@extend_schema(parameters=repo_parameters, tags=["Branches"])
class BranchViewSet(
    BranchViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    queryset = Branch.objects.none()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BranchDetailSerializer
        elif self.action == "list":
            return BranchSerializer

    @extend_schema(summary="Branch list")
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of branches for the specified repository
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Branch detail",
        parameters=[
            OpenApiParameter(
                "name",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="branch name",
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single branch by name.
        Includes head commit information embedded in the response.
        """
        return super().retrieve(request, *args, **kwargs)
