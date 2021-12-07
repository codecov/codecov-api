import asyncio
import logging

from django.db.models import OuterRef, Subquery
from django.shortcuts import Http404, get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from core.models import Commit, Pull
from internal_api.compare.serializers import FlagComparisonSerializer
from internal_api.mixins import RepoPropertyMixin
from internal_api.permissions import RepositoryArtifactPermissions
from internal_api.repo.repository_accessors import RepoAccessors
from services.comparison import Comparison

from .serializers import PullDetailSerializer, PullSerializer

log = logging.getLogger(__name__)


class PullViewSet(
    RepoPropertyMixin,
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["state"]
    ordering_fields = ("pullid",)
    permission_classes = [RepositoryArtifactPermissions]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PullDetailSerializer
        elif self.action == "list":
            return PullSerializer

    def get_object(self):
        pullid = self.kwargs.get("pk")
        return get_object_or_404(self.get_queryset(), pullid=pullid)

    def get_queryset(self):
        return self.repo.pull_requests.annotate(
            base_totals=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("compared_to"), repository=OuterRef("repository")
                ).values("totals")[:1]
            ),
            head_totals=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"), repository=OuterRef("repository")
                ).values("totals")[:1]
            ),
            ci_passed=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"), repository=OuterRef("repository")
                ).values("ci_passed")[:1]
            ),
            most_recent_commiter=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"), repository=OuterRef("repository")
                ).values("author__username")[:1]
            ),
        )
