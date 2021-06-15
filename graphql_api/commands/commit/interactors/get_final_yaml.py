from asgiref.sync import sync_to_async
from shared.yaml import UserYaml
from shared.validation.yaml import validate_yaml
from yaml import safe_load

from services.repo_providers import RepoProviderService
from graphql_api.commands.base import BaseInteractor


class GetFinalYamlInteractor(BaseInteractor):
    async def get_yaml_from_service(self, commit):
        try:
            repository_service = RepoProviderService().get_adapter(
                user=self.current_user, repo=commit.repository
            )
            yaml_on_repo = await repository_service.get_source(
                "codecov.yml", commit.commitid
            )
            yaml_dict = safe_load(yaml_on_repo["content"])
            return validate_yaml(yaml_dict, show_secrets=False)
        except:
            # fetching, parsing, validating the yaml inside the commit can
            # have various exception, which we do not care about to get the final
            # yaml used for a commit, as any error here, the codecov.yaml would not
            # be used, so we return None here
            return None

    @sync_to_async
    def get_yaml_of_owner(self, commit):
        # need to wrap in @sync_to_async as accessing the repository author
        # will call the database
        return commit.repository.author.yaml

    async def execute(self, commit):
        owner_yaml = await self.get_yaml_of_owner(commit)
        commit_yaml = await self.get_yaml_from_service(commit)
        repo_yaml = commit.repository.yaml
        return UserYaml.get_final_yaml(
            owner_yaml=owner_yaml, repo_yaml=repo_yaml, commit_yaml=commit_yaml
        ).to_dict()
