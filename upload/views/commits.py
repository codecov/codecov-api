import logging

from django.forms import ValidationError
from rest_framework.generics import ListCreateAPIView

from codecov_auth.models import Service
from core.models import Commit, Repository
from services.task import TaskService
from upload.serializers import CommitSerializer
from upload.views.helpers import get_repository_from_string
from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from core.models import Commit, Repository
from services.task import TaskService
from upload.serializers import CommitSerializer
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView):
    serializer_class = CommitSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
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

    def get_repo(self) -> Repository:
        service = self.kwargs.get("service")
        try:
            Service(service)
        except ValueError:
            raise ValidationError(f"Service not found: {service}")

        repo_slug = self.kwargs.get("repo")
        repository = get_repository_from_string(Service(service), repo_slug)

        if not repository:
            raise ValidationError(f"Repository not found")
        return repository
