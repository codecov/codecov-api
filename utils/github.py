from shared.github import get_github_integration_token as _get_github_integration_token

from utils.cache import cache


@cache.cache_function(ttl=480)
def get_github_integration_token(service, installation_id=None):
    return _get_github_integration_token(service, integration_id=installation_id)
