import logging

import sentry_sdk
from asgiref.sync import async_to_sync
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from codecov_auth.models import Owner
from core.models import Repository
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
            RepoProviderService().get_adapter(owner=user, repo=repo).get_authenticated
        )()

    @sentry_sdk.trace
    def get_repo_details(
        self, user, repo_name, repo_owner_username, repo_owner_service
    ):
        """
        Returns repo from DB, if it exists.
        """
        try:
            return (
                Repository.objects.all()
                .with_recent_coverage()
                .get(
                    name=repo_name,
                    author__username=repo_owner_username,
                    author__service=repo_owner_service,
                )
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
            owner=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )
        result = async_to_sync(adapter.get_repository)()

        owner, _ = Owner.objects.get_or_create(
            service=repo_owner_service,
            username=result["owner"]["username"],
            service_id=result["owner"]["service_id"],
            defaults={"createstamp": timezone.now()},
        )

        return Repository.objects.get_or_create_from_git_repo(
            git_repo=result["repo"], owner=owner
        )[0]
