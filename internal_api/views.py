from rest_framework import generics
from core.models import Pull, Commit, Repository
from internal_api.serializers import PullSerializer, CommitSerializer, RepoSerializer, ShortParentlessCommitSerializer
from django.shortcuts import Http404

class BaseInternalAPIView(object):

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class PullRequestList(BaseInternalAPIView, generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer


class CommitList(BaseInternalAPIView, generics.ListCreateAPIView):
    queryset = Commit.objects.all()
    serializer_class = ShortParentlessCommitSerializer


class RepoPullRequestList(BaseInternalAPIView, generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer


class RepoCommitList(BaseInternalAPIView, generics.ListCreateAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer


class RepositoryList(BaseInternalAPIView, generics.ListCreateAPIView):
    queryset = Repository.objects.all()
    serializer_class = RepoSerializer


class RepoCommmitDetail(BaseInternalAPIView, generics.RetrieveUpdateAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer

    def get_object(self):
        queryset = self.get_queryset()
        repoid = self.kwargs['repoid']
        commitid = self.kwargs['commitid']
        queryset = queryset.filter(repository_id=repoid)
        queryset = queryset.filter(commitid=commitid)
        try:
            obj = queryset.get()
        except Commit.DoesNotExist:
            raise Http404('No %s matches the given query.' % queryset.model._meta.object_name)
        self.check_object_permissions(self.request, obj)
        return obj
