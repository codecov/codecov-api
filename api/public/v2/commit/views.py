from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins

from api.public.v2.schema import repo_parameters
from api.shared.commit.mixins import CommitsViewSetMixin
from core.models import Commit

from .serializers import CommitDetailSerializer, CommitSerializer


@extend_schema(parameters=repo_parameters, tags=["Commits"])
class CommitsViewSet(
    CommitsViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    queryset = Commit.objects.none()

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({"include_line_coverage": True})
        return context

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CommitDetailSerializer
        elif self.action == "list":
            return CommitSerializer

    @extend_schema(summary="Commit list")
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of commits for the specified repository

        Optionally filterable by:
        * a `branch` name
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Commit detail",
        parameters=[
            OpenApiParameter(
                "commitid",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="commit SHA",
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single commit by commitid (SHA)
        """
        return super().retrieve(request, *args, **kwargs)
