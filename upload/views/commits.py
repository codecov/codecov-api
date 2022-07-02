import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

from core.models import Commit, Repository
from upload.serializers import CommitSerializer

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView):
    serializer_class = CommitSerializer
    queryset = Commit.objects.all()
    permission_classes = [
        AllowAny,
    ]

    def perform_create(self, serializer):
        repo = self.kwargs["repo"]
        repository = Repository.objects.get(name=repo)
        return serializer.save(repository=repository)

    def list(self, request: HttpRequest, repo: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
