import asyncio
from rest_framework import generics, filters
from django.shortcuts import Http404
from internal_api.mixins import RepoFilterMixin
from core.models import Commit
from .serializers import CommitSerializer, ShortParentlessCommitSerializer, ParentlessCommitSerializer


class RepoCommitList(RepoFilterMixin, generics.ListAPIView):
    queryset = Commit.objects.all()
    serializer_class = ShortParentlessCommitSerializer

    def filter_queryset(self, queryset):
        queryset = super(RepoCommitList, self).filter_queryset(queryset)
        return queryset.order_by('-timestamp')


class RepoCommmitDetail(generics.RetrieveAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer

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
