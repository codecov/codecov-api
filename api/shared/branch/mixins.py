from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions

from .filters import BranchFilters


class BranchViewSetMixin(viewsets.GenericViewSet, RepoPropertyMixin):
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = BranchFilters
    ordering_fields = ("updatestamp", "name")
    permission_classes = [RepositoryArtifactPermissions]

    def get_queryset(self):
        return self.repo.branches.order_by(F("updatestamp").desc(nulls_last=True))
