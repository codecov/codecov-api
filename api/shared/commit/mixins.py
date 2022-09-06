from rest_framework import viewsets

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions

from .filters import CommitFilters


class CommitsViewSetMixin(
    viewsets.GenericViewSet,
    RepoPropertyMixin,
):
    filterset_class = CommitFilters
    permission_classes = [RepositoryArtifactPermissions]
    lookup_field = "commitid"

    def get_queryset(self):
        # We don't use the "report" field in this endpoint since it can be many MBs of JSON.
        # Choosing not to fetch it for perf reasons.
        return (
            self.repo.commits.defer("report")
            .select_related("author")
            .order_by("-timestamp")
        )
