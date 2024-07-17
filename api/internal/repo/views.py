import logging

from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins
from rest_framework.exceptions import PermissionDenied

from api.internal.repo.filter import RepositoryOrderingFilter
from api.shared.repo.filter import RepositoryFilters
from api.shared.repo.mixins import RepositoryViewSetMixin

from .serializers import (
    RepoDetailsSerializer,
    RepoWithMetricsSerializer,
)

log = logging.getLogger(__name__)


class RepositoryViewSet(
    RepositoryViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    filter_backends = (
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
        RepositoryOrderingFilter,
    )
    filterset_class = RepositoryFilters
    search_fields = ("name",)
    ordering_fields = (
        "updatestamp",
        "name",
        "latest_coverage_change",
        "coverage",
        "lines",
        "hits",
        "partials",
        "misses",
        "complexity",
    )

    def get_serializer_class(self):
        if self.action == "list":
            return RepoWithMetricsSerializer
        return RepoDetailsSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        if self.action != "list":
            context.update({"can_edit": self.can_edit, "can_view": self.can_view})
        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "list":
            before_date = self.request.query_params.get(
                "before_date", timezone.now().isoformat()
            )
            branch = self.request.query_params.get("branch", None)

            queryset = queryset.with_latest_commit_totals_before(
                before_date=before_date, branch=branch, include_previous_totals=True
            ).with_latest_coverage_change()

            if self.request.query_params.get("exclude_uncovered", False):
                queryset = queryset.exclude_uncovered()

        return queryset

    def perform_update(self, serializer):
        # Check repo limits for users with legacy plans
        owner = self.owner
        if serializer.validated_data.get("active"):
            if owner.has_legacy_plan and owner.repo_credits <= 0:
                raise PermissionDenied("Private repository limit reached.")
        return super().perform_update(serializer)
