import asyncio
from rest_framework import generics
from django.shortcuts import Http404

from services.archive import ReportService
from internal_api.mixins import FilterByRepoMixin, RepoSlugUrlMixin
from core.models import Commit
from .serializers import CommitWithParentSerializer, FlagSerializer, CommitSerializer
from .filters import CommitFilters
from internal_api.permissions import RepositoryArtifactPermissions


class RepoCommitList(FilterByRepoMixin, generics.ListAPIView):
    filterset_class = CommitFilters
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer
    permission_classes = [RepositoryArtifactPermissions]

    def filter_queryset(self, queryset):
        queryset = super(RepoCommitList, self).filter_queryset(queryset)
        return queryset.order_by('-timestamp')
