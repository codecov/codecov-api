from rest_framework import generics
from core.models import Pull, Commit, Repository
from internal_api.serializers import PullSerializer, CommitSerializer, RepoSerializer


# Create your views here.

class PullRequestList(generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer


class CommitList(generics.ListCreateAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class RepoPullRequestList(generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer


class RepoCommitList(generics.ListCreateAPIView):
    queryset = Commit.objects.all()
    serializer_class = CommitSerializer


class RepositoryList(generics.ListCreateAPIView):
    queryset = Repository.objects.all()
    serializer_class = RepoSerializer
