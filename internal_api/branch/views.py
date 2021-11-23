from django.db.models import F, OuterRef, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from core.models import Branch, Commit
from internal_api.mixins import RepoPropertyMixin
from internal_api.permissions import RepositoryArtifactPermissions

from .filters import BranchFilters
from .serializers import BranchSerializer


class BranchViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, RepoPropertyMixin):
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = BranchFilters
    ordering_fields = ("updatestamp", "name")
    permission_classes = [RepositoryArtifactPermissions]

    def get_queryset(self):
        return self.repo.branches.annotate(
            most_recent_commiter=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"),
                    repository_id=OuterRef("repository__repoid"),
                ).values("author__username")[:1]
            )
        ).order_by(F("updatestamp").desc(nulls_last=True))
