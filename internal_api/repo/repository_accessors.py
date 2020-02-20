import asyncio

from django.core.exceptions import ObjectDoesNotExist

from codecov_auth.models import Owner
from core.models import Repository
from services.repo_providers import RepoProviderService


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
        return asyncio.run(RepoProviderService().get_adapter(
            owner=user,
            repo=repo
        ).get_authenticated())

    def get_repo_details(self, user, repo_name, org_name):
        """
        Checks if repo exists in DB, and if it doesn't, tries to fetch it from provider.
        """
        try:
            owner = Owner.objects.get(service=user.service, username=org_name)
            repo = Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            repo = self.fetch_repo(user, repo_name, org_name)
            # raise NotFound(detail="Repository {} for org {} not found ".format(repo_name, org_name))
        return repo

    def fetch_repo(self, user, repo_name, org_name):
        """
            Fetch repository details for the provider and update the DB with new information.
        """
        result = asyncio.run(RepoProviderService().get_by_name(user, repo_name=repo_name,
                                                               repo_owner=org_name).get_repository())
        fork = result['repo'].pop('fork', None)
        repo = Repository(**result['repo'])
        owner = Owner(**result['owner'])
        repo.author = owner
        if fork:
            fork_repo = Repository(**fork['repo'])
            fork_owner = Owner(**fork['owner'])
            fork_repo.author = fork_owner
            repo.fork = fork_repo
        # TODO: save this repo to the DB, and generate a upload token for it if doesn't exist
        # https://github.com/codecov/codecov.io/blob/master/src/sql/main/functions/refresh_repos.sql#L53-L149
        return repo
