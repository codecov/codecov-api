from typing import List

from core.models import Repository


class RepositoryAsUser(object):
    def __init__(self, repository):
        self._repository = repository

    def is_authenticated(self):
        return True


class RepositoryAuthInterface(object):
    def get_scopes():
        raise NotImplementedError()

    def get_repositories() -> List[Repository]:
        raise NotImplementedError()

    def allows_repo(self, repository: Repository) -> bool:
        raise NotImplementedError()
