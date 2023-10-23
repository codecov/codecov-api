from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.models import Repository
from graphql_api.types.enums.enums import CiProvider


class ConfigureRepoViaPRInteractor(BaseInteractor):

    supported_ci_providers = [CiProvider.GITHUB_ACTIONS]

    @sync_to_async
    def execute(self, repo_name: str, owner_username: str, ci_provider: CiProvider):
        author = Owner.objects.filter(
            username=owner_username, service=self.service
        ).first()
        repo = (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=author, name=repo_name)
            .first()
        )
        if not repo:
            raise ValidationError("Repo not found")

        if ci_provider not in self.supported_ci_providers:
            raise ValidationError(f"Provider {ci_provider} is not supported")

        try:
            # TODO: Enqueue task to generate the config PR
            raise NotImplementedError()
        except NotImplementedError:
            result = False

        return result
