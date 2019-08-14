import asyncio
from rest_framework import generics
from django.shortcuts import Http404

from archive.services import ReportService
from internal_api.mixins import FilterByRepoMixin, RepoSlugUrlMixin
from core.models import Commit
from .serializers import CommitWithParentSerializer, FlagSerializer, CommitSerializer


class RepoCommitList(FilterByRepoMixin, generics.ListAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer

    def filter_queryset(self, queryset):
        queryset = super(RepoCommitList, self).filter_queryset(queryset)
        return queryset.order_by('-timestamp')


class RepoCommmitDetail(generics.RetrieveAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitWithParentSerializer

    def get_object(self):
        queryset = self.get_queryset()
        asyncio.set_event_loop(asyncio.new_event_loop())
        repoid = self.kwargs['repoid']
        commitid = self.kwargs['commitid']
        queryset = queryset.filter(
            repository_id=repoid,
            repository__owner=self.request.user,
            commitid=commitid
        )
        try:
            obj = queryset.get()
        except Commit.DoesNotExist:
            raise Http404('No %s matches the given query.' %
                          queryset.model._meta.object_name)
        self.check_object_permissions(self.request, obj)
        return obj


class RepoCommitFlags(RepoSlugUrlMixin, generics.ListAPIView):
    serializer_class = FlagSerializer

    def get_commit(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        commitid = self.kwargs['commitid']
        repo = self.get_repo()
        queryset = Commit.objects.filter(
            repository_id=repo.repoid,
            commitid=commitid
        )
        try:
            obj = queryset.get()
        except Commit.DoesNotExist:
            raise Http404('No %s matches the given query.' %
                          queryset.model._meta.object_name)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        commit = self.get_commit()
        report = ReportService().build_report_from_commit(commit)
        return list(report.flags.values())
