from django.db.models import Subquery, OuterRef

from rest_framework import viewsets, mixins, filters

from django_filters.rest_framework import DjangoFilterBackend

from core.models import Branch, Commit

from internal_api.mixins import RepoPropertyMixin
from internal_api.permissions import RepositoryArtifactPermissions

from .serializers import BranchSerializer
from .filters import BranchFilters


class BranchViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, RepoPropertyMixin):
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = BranchFilters
    ordering_fields = ('updatestamp', 'name')
    ordering = ['-updatestamp']
    permission_classes = [RepositoryArtifactPermissions]

    def get_queryset(self):
        return self.repo.branches.annotate(
            most_recent_commiter=Subquery(
                Commit.objects.filter(
                    branch=OuterRef('name'),
                    repository_id=OuterRef('repository__repoid')
                ).order_by('-timestamp').values('author__username')[:1]
            )
        )
