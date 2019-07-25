import asyncio

from django.core.exceptions import ObjectDoesNotExist

from codecov_auth.models import Owner
from core.models import Repository
from repo_providers.services import RepoProviderService


class RepoAccessors(object):

    def get_repo_permissions(self, user, repo_name, org_name):
        """
            Returns repo permissions information from the provider
        :param repo_name:
        :param org_name:
        :return:
        """
        can_view, can_edit = asyncio.run(RepoProviderService().get_by_name(user, repo_name=repo_name,
                                                                           repo_owner=org_name).get_authenticated())
        return can_view, can_edit

    def get_repo_details(self, user, repo_name, org_name):
        """
            Check if the repo exists in codecov db to return repo stats
        """
        try:
            owner = Owner.objects.get(service=user.service, username=org_name)
            repo = Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            print("Not found locally - let's check with the provider... ")
            repo = fetch_repo(user, repo_name, org_name)
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
