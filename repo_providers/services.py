from torngit import get

from codecov_auth.models import Owner
from core.models import Repository
from utils.encryption import encryptor


class RepoProviderService(object):

    @staticmethod
    def get_adapter(owner: Owner, repo: Repository):
        """
            Return the corresponding implementation for calling the repository provider
        :param owner: :class:`codecov_auth.models.Owner`
        :param repo: :class:`core.models.Repository`
        :return:
        """
        adapter_params = dict(
            repo=dict(name=repo.name),
            owner=dict(username=repo.author.username),
            token=encryptor.decrypt_token(owner.oauth_token)
        )
        return get(
            owner.service,
            **adapter_params
        )

    @staticmethod
    def get_by_name(owner, repo_name, repo_owner):
        """
            Return the corresponding implementation for calling the repository provider
        :param owner:
        :param repo_name:
        :param repo_owner:
        :return:
        """
        adapter_params = dict(
            repo=dict(name=repo_name),
            owner=dict(username=repo_owner),
            token=encryptor.decrypt_token(owner.oauth_token)
        )
        return get(
            owner.service,
            **adapter_params
        )