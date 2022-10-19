from asgiref.sync import async_to_sync, sync_to_async
from shared.yaml import UserYaml, fetch_current_yaml_from_provider_via_reference
from shared.yaml.validation import validate_yaml
from yaml import safe_load

from codecov.commands.base import BaseInteractor
from services.repo_providers import RepoProviderService


class GetFinalYamlInteractor(BaseInteractor):
    def get_yaml_from_service(self, commit):
        try:
            repository_service = RepoProviderService().get_adapter(
                user=self.current_user, repo=commit.repository
            )
            yaml_on_repo = async_to_sync(
                fetch_current_yaml_from_provider_via_reference
            )(commit.commitid, repository_service)
            yaml_dict = safe_load(yaml_on_repo)
            return validate_yaml(yaml_dict, show_secrets_for=None)
        except:
            # fetching, parsing, validating the yaml inside the commit can
            # have various exception, which we do not care about to get the final
            # yaml used for a commit, as any error here, the codecov.yaml would not
            # be used, so we return None here
            return None

    @sync_to_async
    def execute(self, commit):
        return UserYaml.get_final_yaml(
            owner_yaml=commit.repository.author.yaml,
            repo_yaml=commit.repository.yaml,
            commit_yaml=self.get_yaml_from_service(commit),
        ).to_dict()
