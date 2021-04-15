from rest_framework import viewsets, mixins

from internal_api.mixins import RepoPropertyMixin
from internal_api.permissions import RepositoryArtifactPermissions
from core.models import Commit

from .serializers import CommitSerializer
from .filters import CommitFilters


class CommitsViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, RepoPropertyMixin):
    filterset_class = CommitFilters
    serializer_class = CommitSerializer
    permission_classes = [RepositoryArtifactPermissions]

    def get_queryset(self):
        # We don't use the "report" field in this endpoint and it can be many MBs of JSON choosing not to
        # fetch it for perf reasons
        return (
            self.repo.commits.defer("report")
            .select_related("author")
            .order_by("-timestamp")
        )
