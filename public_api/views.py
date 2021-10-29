import logging

from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from codecov_auth.authentication.repo_auth import RepositoryLegacyTokenAuthentication
from core.models import Commit, Pull
from internal_api.mixins import RepoPropertyMixin
from services.task import TaskService

from .permissions import PullUpdatePermission
from .serializers import PullSerializer

log = logging.getLogger(__name__)


class PullViewSet(
    RepoPropertyMixin,
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = PullSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["state"]
    ordering_fields = ("pullid",)
    authentication_classes = [RepositoryLegacyTokenAuthentication]
    permission_classes = [PullUpdatePermission]

    def get_object(self):
        pullid = self.kwargs.get("pk")
        if self.request.method == "PUT":
            # Note: We create a new pull if needed to make sure that they can be updated
            # with a base before the upload has finished processing.
            obj, _created = self.get_queryset().get_or_create(
                repository=self.repo, pullid=pullid
            )
            return obj
        return get_object_or_404(self.get_queryset(), pullid=pullid)

    def get_queryset(self):
        return self.repo.pull_requests.annotate(
            ci_passed=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"), repository=OuterRef("repository")
                ).values("ci_passed")[:1]
            ),
        )

    def perform_update(self, serializer):
        result = super().perform_update(serializer)
        TaskService().pulls_sync(repoid=self.repo.repoid, pullid=self.kwargs.get("pk"))
        return result
