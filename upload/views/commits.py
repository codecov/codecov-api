import logging

from django.forms import ValidationError
from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

from core.models import Commit, Repository
from upload.serializers import CommitSerializer

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView):
    serializer_class = CommitSerializer
    permission_classes = [
        # TODO: change to the correct permission class when implemented
        AllowAny,
    ]

    def get_queryset(self):
        # TODO: This is not the final implementation.
        repository = self.get_repo()
        return Commit.objects.filter(repository=repository)

    def perform_create(self, serializer):
        repository = self.get_repo()
        return serializer.save(repository=repository)

    def list(self, request: HttpRequest, repo: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def get_repo(self) -> Repository:
        # TODO this is not final - how is getting the repo is still in discuss
        repoid = self.kwargs["repo"]
        try:
            repository = Repository.objects.get(name=repoid)
            return repository
        except Repository.DoesNotExist:
            raise ValidationError(f"Repository {repoid} not found")
