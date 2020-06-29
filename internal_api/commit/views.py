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
        return self.repo.commits.select_related("author").order_by("-timestamp")
