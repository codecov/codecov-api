import logging
from os import getenv
from typing import Callable, Dict

from asgiref.sync import sync_to_async
from django.conf import settings
from shared.encryption.token import encode_token
from shared.torngit import get

from codecov_auth.models import Owner, Service
from core.models import Repository
from utils.config import get_config
from utils.encryption import encryptor

log = logging.getLogger(__name__)


class TorngitInitializationFailed(Exception):
    """
    Exception when initializing the torngit provider object.
    """

    pass


def get_token_refresh_callback(user: Owner, service: Service) -> Callable[[Dict], None]:
    """
    Produces a callback function that will encode and update the oauth token of a user.
    This callback is passed to the TorngitAdapter for the service.
    """
    if service != Service.GITLAB and service != Service.GITLAB_ENTERPRISE:
        return None

    @sync_to_async
    def callback(new_token: Dict) -> None:
        log.info(
            "Saving new token after refresh",
            extra=dict(owner=user.username, ownerid=user.ownerid),
        )
        string_to_save = encode_token(new_token)
        user.oauth_token = encryptor.encode(string_to_save).decode()
        user.save()

    return callback


def get_generic_adapter_params(user, service, use_ssl=False, token=None):
    if use_ssl:
        verify_ssl = (
            get_config(service, "ssl_pem")
            if get_config(service, "verify_ssl") is not False
            else getenv("REQUESTS_CA_BUNDLE")
        )
    else:
        verify_ssl = None

    if token is None:
        if user.is_authenticated and user.oauth_token is not None:
            token = encryptor.decrypt_token(user.oauth_token)
            token["username"] = user.username
        else:
            token = {"key": getattr(settings, f"{service.upper()}_BOT_KEY")}
    return dict(
        verify_ssl=verify_ssl,
        token=token,
        timeouts=(5, 15),
        oauth_consumer_token=dict(
            key=getattr(settings, f"{service.upper()}_CLIENT_ID", "unknown"),
            secret=getattr(settings, f"{service.upper()}_CLIENT_SECRET", "unknown"),
        ),
        on_token_refresh=get_token_refresh_callback(user, service),
    )


def get_provider(service, adapter_params):
    provider = get(service, **adapter_params)
    if provider:
        return provider
    else:
        raise TorngitInitializationFailed()


class RepoProviderService(object):
    def get_adapter(self, user: Owner, repo: Repository, use_ssl=False, token=None):
        """
        Return the corresponding implementation for calling the repository provider

        :param user: :class:`codecov_auth.models.Owner`
        :param repo: :class:`core.models.Repository`
        :return:
        :raises: TorngitInitializationFailed
        """
        generic_adapter_params = get_generic_adapter_params(
            user, repo.author.service, use_ssl, token
        )
        owner_and_repo_params = {
            "repo": {
                "name": repo.name,
                "using_integration": repo.using_integration or False,
                "service_id": repo.service_id,
                "private": repo.private,
                "repoid": repo.repoid,
            },
            "owner": {
                "username": repo.author.username,
                "service_id": repo.author.service_id,
            },
        }

        return get_provider(
            repo.author.service, {**generic_adapter_params, **owner_and_repo_params}
        )

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
        generic_adapter_params = get_generic_adapter_params(user, repo_owner_service)
        owner_and_repo_params = {
            "repo": {"name": repo_name},
            "owner": {"username": repo_owner_username},
        }
        return get_provider(
            repo_owner_service, {**generic_adapter_params, **owner_and_repo_params}
        )
