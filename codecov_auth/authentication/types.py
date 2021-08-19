from enum import Enum, auto


class RepositoryAsUser(object):
    def __init__(self, repository):
        self._repository = repository

    def is_authenticated(self):
        return True


class RepositoryAuthInterface(object):

    def get_scopes():
        raise NotImplementedError()

    def get_repositories():
        raise NotImplementedError()


class LegacyTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, auth_data):
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self):
        return ["upload"]

    def get_repositories(self):
        return [self._repository]
