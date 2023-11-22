from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets

from api.public.v2.schema import repo_parameters
from api.shared.commit.mixins import CommitsViewSetMixin
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from core.models import Commit
from reports.models import ReportSession

from .serializers import (
    CommitDetailSerializer,
    CommitSerializer,
    CommitUploadsSerializer,
)

commits_parameters = [
    OpenApiParameter(
        "commitid",
        OpenApiTypes.STR,
        OpenApiParameter.PATH,
        description="commit SHA",
    ),
]


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

    @extend_schema(summary="Commit detail", parameters=commits_parameters)
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single commit by commitid (SHA)
        """
        return super().retrieve(request, *args, **kwargs)


@extend_schema(parameters=repo_parameters, tags=["Commits"])
class CommitsUploadsViewSet(
    viewsets.GenericViewSet,
    RepoPropertyMixin,
    mixins.ListModelMixin,
):
    permission_classes = [RepositoryArtifactPermissions]
    serializer_class = CommitUploadsSerializer

    def get_queryset(self):
        commit = self.get_commit(self.kwargs["commitid"])
        return ReportSession.objects.filter(report__commit=commit.id).select_related(
            "uploadleveltotals"
        )

    @extend_schema(summary="Commit uploads", parameters=commits_parameters)
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of uploads for a single commit by commitid (SHA)
        """
        return super().list(request, *args, **kwargs)
