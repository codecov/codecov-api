from shared.torngit import get

from codecov_auth.models import Owner
from core.models import Repository
from utils.encryption import encryptor
from utils.config import get_config


class TorngitInitializationFailed(Exception):
    """
        Exception when initializing the torngit provider object.
    """
    pass


class RepoProviderService(object):
    def get_adapter(self, owner: Owner, repo: Repository):
        """
        Return the corresponding implementation for calling the repository provider

        :param owner: :class:`codecov_auth.models.Owner`
        :param repo: :class:`core.models.Repository`
        :return:
        :raises: TorngitInitializationFailed
        """
        adapter_params = dict(
            repo=dict(
                name=repo.name,
                using_integration=repo.using_integration or False,
                service_id=repo.service_id,
                private=repo.private
            ),
            owner=dict(username=repo.author.username),
            token=encryptor.decrypt_token(owner.oauth_token),
            oauth_consumer_token=dict(
                key=get_config(owner.service, 'client_id'),
                secret=get_config(owner.service, 'client_secret')
            )
        )
        return self._get_provider(owner.service, adapter_params)

    def get_by_name(self, owner, repo_name, repo_owner):
        """
        Return the corresponding implementation for calling the repository provider

        :param owner:
        :param repo_name:
        :param repo_owner:
        :return:
        :raises: TorngitInitializationFailed
        """
        adapter_params = dict(
            repo=dict(name=repo_name),
            owner=dict(username=repo_owner),
            token=encryptor.decrypt_token(owner.oauth_token)
        )
        return self._get_provider(
            owner.service,
            adapter_params
        )

    @classmethod
    def _get_provider(cls, service, adapter_params):
        provider = get(
            service,
            **adapter_params
        )
        if provider:
            return provider
        else:
            raise TorngitInitializationFailed()

