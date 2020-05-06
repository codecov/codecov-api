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
        Returns repo from DB, if it exists.
        """
        try:
            owner = Owner.objects.get(service=user.service, username=org_name)
            repo = Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            repo = None
        return repo

    def fetch_from_git_and_create_repo(self, user, repo_name, org_name):
        """
            Fetch repository details for the provider and update the DB with new information.
        """
        # Try to fetch the repo from the git provider using shared.torngit
        result = asyncio.run(RepoProviderService().get_by_name(user, repo_name=repo_name,
                                                               repo_owner=org_name).get_repository())
        git_repo = result['repo']
        git_repo_owner = result['owner']

        owner, _ = Owner.objects.get_or_create(
            service=user.service,
            username=git_repo_owner['username'],
            service_id=git_repo_owner['service_id']
        )
        created_repo, _ = Repository.objects.get_or_create(
            author=owner,
            service_id=git_repo['service_id'],
            private=git_repo['private'],
            branch=git_repo['branch'],
            name=git_repo['name']
        )

        # If this is a fork, create the forked repo and save it to the new repo
        if git_repo.get('fork'):
            git_repo_fork = git_repo['fork']['repo']
            git_repo_fork_owner = git_repo['fork']['owner']

            fork_owner, _ = Owner.objects.get_or_create(
                service=user.service,
                username=git_repo_fork_owner['username'],
                service_id=git_repo_fork_owner['service_id']
            )
            fork, _ = Repository.objects.get_or_create(
                author=fork_owner,
                service_id=git_repo_fork['service_id'],
                private=git_repo_fork['private'],
                branch=git_repo_fork['branch'],
                name=git_repo_fork['name']
            )
            created_repo.fork = fork
            created_repo.save()

        return created_repo
