import logging

from django.forms import ValidationError
from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

from core.models import Commit, Repository
from services.task import TaskService
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
        # TODO we should make sure that the commit is not already there, otherwise we'll get 500
        repository = self.get_repo()
        commit = serializer.save(repository=repository)
        TaskService().update_commit(
            commitid=commit.commitid, repoid=commit.repository.repoid
        )
        return commit

    def list(self, request: HttpRequest, repo: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def get_repo(self) -> Repository:
        # TODO this is not final - how is getting the repo is still in discuss
        repoid = self.kwargs.get("repo")
        try:
            # TODO fix this: this might return multiple repos
            repository = Repository.objects.get(name=repoid)
            return repository
        except Repository.DoesNotExist:
            raise ValidationError(f"Repository {repoid} not found")
