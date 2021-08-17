from enum import Enum, auto


class AuthSource(Enum):
    legacy_token = auto()


class RepositoryAsUser(object):
    def __init__(self, repository):
        self._repository = repository

    def is_authenticated(self):
        return True


class RepositoryAuth(object):
    def __init__(self, repository, token_source: AuthSource, auth_data):
        self._token_source = token_source
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self):
        if self._token_source == AuthSource.legacy_token:
            return ["upload"]
        return False

    def get_repositories(self):
        return [self._repository]
