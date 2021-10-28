from rest_framework import mixins, viewsets

from core.models import Commit
from internal_api.mixins import RepoPropertyMixin
from internal_api.permissions import RepositoryArtifactPermissions

from .filters import CommitFilters
from .serializers import CommitSerializer


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
