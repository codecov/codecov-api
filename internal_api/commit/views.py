import asyncio
from rest_framework import generics
from django.shortcuts import Http404
from internal_api.views import RepoFilter
from .models import Commit
from .serializers import CommitSerializer, ShortParentlessCommitSerializer


class RepoCommitsView(RepoFilter, generics.ListCreateAPIView):
    queryset = Commit.objects.all()
    serializer_class = ShortParentlessCommitSerializer


class RepoCommmitDetail(generics.RetrieveUpdateAPIView):
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
            raise Http404('No %s matches the given query.' % queryset.model._meta.object_name)
        self.check_object_permissions(self.request, obj)
        return obj
