import logging
import uuid

from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from api.internal.repo.filter import RepositoryOrderingFilter
from api.shared.repo.filter import RepositoryFilters
from api.shared.repo.mixins import RepositoryViewSetMixin
from services.decorators import torngit_safe
from services.repo_providers import RepoProviderService
from services.segment import SegmentService
from services.task import TaskService

from .repository_actions import create_webhook_on_provider, delete_webhook_on_provider
from .serializers import (
    RepoDetailsSerializer,
    RepoWithMetricsSerializer,
    SecretStringPayloadSerializer,
)
from .utils import encode_secret_string

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

    def destroy(self, request, *args, **kwargs):
        SegmentService().account_deleted_repository(
            self.request.user.ownerid, self.get_object()
        )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["patch"], url_path="regenerate-upload-token")
    def regenerate_upload_token(self, request, *args, **kwargs):
        repo = self.get_object()
        repo.upload_token = uuid.uuid4()
        repo.save()
        return Response(self.get_serializer(repo).data)

    @action(detail=True, methods=["patch"])
    def erase(self, request, *args, **kwargs):
        self._assert_is_admin()
        repo = self.get_object()
        TaskService().delete_timeseries(repository_id=repo.repoid)
        repo.flush()
        SegmentService().account_erased_repository(self.request.user.ownerid, repo)
        return Response(self.get_serializer(repo).data)

    @action(detail=True, methods=["post"])
    def encode(self, request, *args, **kwargs):
        serializer = SecretStringPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        owner, repo = self.owner, self.get_object()

        to_encode = "/".join(
            (
                owner.service,
                owner.service_id,
                repo.service_id,
                serializer.validated_data["value"],
            )
        )

        return Response(
            SecretStringPayloadSerializer(
                {"value": encode_secret_string(to_encode)}
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["put"], url_path="reset-webhook")
    @torngit_safe
    def reset_webhook(self, request, *args, **kwargs):
        repo = self.get_object()
        repository_service = RepoProviderService().get_adapter(self.request.user, repo)

        if repo.hookid:
            delete_webhook_on_provider(repository_service, repo)
            repo.hookid = None
            repo.save()

        repo.hookid = create_webhook_on_provider(repository_service, repo)
        repo.save()

        return Response(self.get_serializer(repo).data, status=status.HTTP_200_OK)
