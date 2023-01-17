from typing import Dict, Optional

from asgiref.sync import async_to_sync
from shared.yaml import UserYaml, fetch_current_yaml_from_provider_via_reference
from shared.yaml.user_yaml import UserYaml
from shared.yaml.validation import validate_yaml
from yaml import safe_load

from codecov_auth.models import Owner
from core.models import Commit
from services.repo_providers import RepoProviderService


def fetch_commit_yaml(commit: Commit, user: Owner) -> Optional[Dict]:
    """
    Fetches the codecov.yaml file for a particular commit from the service provider.
    Service provider API request is made on behalf of the given `user`.
    """
    try:
        repository_service = RepoProviderService().get_adapter(
            user=user, repo=commit.repository
        )
        yaml_str = async_to_sync(fetch_current_yaml_from_provider_via_reference)(
            commit.commitid, repository_service
        )
        yaml_dict = safe_load(yaml_str)
        return validate_yaml(yaml_dict, show_secrets_for=None)
    except:
        # fetching, parsing, validating the yaml inside the commit can
        # have various exceptions, which we do not care about to get the final
        # yaml used for a commit, as any error here, the codecov.yaml would not
        # be used, so we return None here
        return None


def final_commit_yaml(commit: Commit, user: Owner) -> UserYaml:
    return UserYaml.get_final_yaml(
        owner_yaml=commit.repository.author.yaml,
        repo_yaml=commit.repository.yaml,
        commit_yaml=fetch_commit_yaml(commit, user),
    )
