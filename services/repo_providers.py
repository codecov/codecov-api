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
    def get_adapter(self, user: Owner, repo: Repository):
        """
        Return the corresponding implementation for calling the repository provider

        :param user: :class:`codecov_auth.models.Owner`
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
            token=encryptor.decrypt_token(user.oauth_token) if user.oauth_token else None,
            oauth_consumer_token=dict(
                key=get_config(repo.author.service, 'client_id'),
                secret=get_config(repo.author.service, 'client_secret')
            )
        )
        return self._get_provider(repo.author.service, adapter_params)

    def get_by_name(self, user, repo_name, repo_owner_username, repo_owner_service):
        """
        Return the corresponding implementation for calling the repository provider

        :param user: Owner object of the user
        :param repo_name: string, name of the repo
        :param owner: Owner, owner of the repo in question
        :repo_owner_service: 'github', 'gitlab' etc
        :return:
        :raises: TorngitInitializationFailed
        """
        adapter_params = dict(
            repo=dict(name=repo_name),
            owner=dict(username=repo_owner_username),
            token=encryptor.decrypt_token(user.oauth_token)
        )
        return self._get_provider(
            service=repo_owner_service,
            adapter_params=adapter_params
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
