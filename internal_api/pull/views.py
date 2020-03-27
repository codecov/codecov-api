import asyncio

from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import Http404, get_object_or_404
from django.db.models import Subquery, OuterRef
from rest_framework import generics, filters
from rest_framework import viewsets, mixins
from rest_framework.exceptions import PermissionDenied

from internal_api.mixins import RepoSlugUrlMixin
from internal_api.repo.repository_accessors import RepoAccessors
from internal_api.compare.serializers import FlagComparisonSerializer
from services.comparison import get_comparison_from_pull_request
from core.models import Pull, Commit
from .serializers import PullSerializer, PullDetailSerializer

import logging


log = logging.getLogger(__name__)


class RepoPullViewset(
    RepoSlugUrlMixin,
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin
):
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['state']
    ordering_fields = ('updatestamp', 'head__timestamp')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PullDetailSerializer
        elif self.action == 'list':
            return PullSerializer

    def get_object(self):
        pullid = self.kwargs.get("pk")
        obj = get_object_or_404(self.get_queryset(), pullid=pullid)
        return obj

    def _check_permissions(self, repo):
        # TODO: roll this into shared permssions class, use DRF permissions engine
        can_view, _ = RepoAccessors().get_repo_permissions(self.request.user, repo)
        if not can_view:
            raise PermissionDenied(detail="You do not have permissions to view this repo")

    def get_queryset(self):
        repo = self.get_repo()
        self._check_permissions(repo)

        return Pull.objects.filter(
            repository=repo
        ).annotate(
            base_totals=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("base"),
                    repository=OuterRef('repository')
                ).values('totals')[:1]
            ),
            head_totals=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"),
                    repository=OuterRef('repository')
                ).values('totals')[:1]
            ),
            ci_passed=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"),
                    repository=OuterRef('repository')
                ).values('ci_passed')[:1]
            ),
            most_recent_commiter=Subquery(
                Commit.objects.filter(
                    commitid=OuterRef("head"),
                    repository=OuterRef('repository')
                ).values('author__username')[:1]
            )
        )


class RepoPullFlagsList(RepoSlugUrlMixin, generics.ListCreateAPIView):
    serializer_class = FlagComparisonSerializer

    def get_comparison(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        user = self.request.user
        repo = self.get_repo()
        pullid = self.kwargs['pullid']
        pull_requests = Pull.objects.filter(
            repository=repo,
            pullid=pullid
        )
        try:
            obj = pull_requests.get()
        except Pull.DoesNotExist:
            raise Http404('No pull matches the given query.')

        try:
            return get_comparison_from_pull_request(obj, user)
        except Commit.DoesNotExist:
            raise Http404("Pull base or head references nonexistant commit.")

    def get_queryset(self):
        comparison = self.get_comparison()
        return list(
            comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags
        )
