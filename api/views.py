import logging

from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Subquery, OuterRef
from rest_framework import filters
from rest_framework import viewsets, mixins

from internal_api.mixins import RepoPropertyMixin
from core.models import Pull, Commit
from .serializers import PullSerializer
from internal_api.permissions import BasePickingPermissions


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
    permission_classes = [BasePickingPermissions]

    def get_object(self):
        pullid = self.kwargs.get("pk")
        return get_object_or_404(self.get_queryset(), pullid=pullid)

    def get_queryset(self):
        return self.repo.pull_requests.annotate(
            ci_passed=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"), repository=OuterRef("repository")
                ).values("ci_passed")[:1]
            ),
        )
