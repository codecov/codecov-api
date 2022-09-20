import asyncio
import logging

from asgiref.sync import async_to_sync
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import APIException, PermissionDenied
from shared.torngit.exceptions import TorngitClientError

from codecov_auth.models import Owner
from core.models import Repository
from services.decorators import torngit_safe
from services.repo_providers import RepoProviderService

log = logging.getLogger(__name__)


class RepoAccessors:
    """
    Easily mockable wrappers for running torngit coroutines.
    """

    def get_repo_permissions(self, user, repo):
        """
        Returns repo permissions information from the provider

        :param repo_name:
        :param org_name:
        :return:
        """
        if user == repo.author:
            return True, True
        return async_to_sync(
            RepoProviderService().get_adapter(user=user, repo=repo).get_authenticated
        )()

    def get_repo_details(
        self, user, repo_name, repo_owner_username, repo_owner_service
    ):
        """
        Returns repo from DB, if it exists.
        """
        try:
            return Repository.objects.get(
                name=repo_name,
                author__username=repo_owner_username,
                author__service=repo_owner_service,
            )
        except ObjectDoesNotExist:
            repo = None
        return repo

    def fetch_from_git_and_create_repo(
        self, user, repo_name, repo_owner_username, repo_owner_service
    ):
        """
        Fetch repository details for the provider and update the DB with new information.
        """
        # Try to fetch the repo from the git provider using shared.torngit
        adapter = RepoProviderService().get_by_name(
            user=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )
        result = async_to_sync(adapter.get_repository)()

        owner, _ = Owner.objects.get_or_create(
            service=repo_owner_service,
            username=result["owner"]["username"],
            service_id=result["owner"]["service_id"],
        )

        return Repository.objects.get_or_create_from_git_repo(
            git_repo=result["repo"], owner=owner
        )[0]
