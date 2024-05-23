import enum
from functools import lru_cache
from typing import Dict, Optional

from asgiref.sync import async_to_sync
from shared.yaml import UserYaml, fetch_current_yaml_from_provider_via_reference
from shared.yaml.validation import validate_yaml
from yaml import safe_load

from codecov_auth.models import Owner, get_config
from core.models import Commit
from services.repo_providers import RepoProviderService


class YamlStates(enum.Enum):
    DEFAULT = "default"


def fetch_commit_yaml(commit: Commit, owner: Owner) -> Optional[Dict]:
    """
    Fetches the codecov.yaml file for a particular commit from the service provider.
    Service provider API request is made on behalf of the given `owner`.
    """
    try:
        repository_service = RepoProviderService().get_adapter(
            owner=owner, repo=commit.repository
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


@lru_cache()
# TODO: make this use the Redis cache logic in 'shared' once it's there
def final_commit_yaml(commit: Commit, owner: Owner) -> UserYaml:
    return UserYaml.get_final_yaml(
        owner_yaml=commit.repository.author.yaml,
        repo_yaml=commit.repository.yaml,
        commit_yaml=fetch_commit_yaml(commit, owner),
    )


def get_yaml_state(yaml: UserYaml) -> YamlStates:
    if yaml == get_config("site", default={}):
        return YamlStates.DEFAULT
