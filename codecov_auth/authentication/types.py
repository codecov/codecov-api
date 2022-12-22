from typing import List

from django.contrib.auth.models import Group, Permission
from django.db.models.manager import EmptyManager

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


class GlobalUser(object):
    id = None
    pk = None
    is_staff = False
    is_active = False
    is_superuser = False
    is_global_user = True
    _groups = EmptyManager(Group)
    _user_permissions = EmptyManager(Permission)

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return False

    @property
    def groups(self):
        return False

    @property
    def user_permissions(self):
        return False

    def get_user_permissions(self, obj=None):
        return False

    def get_group_permissions(self, obj=None):
        return False

    def get_all_permissions(self, obj=None):
        return False

    def has_perm(self, perm, obj=None):
        return False

    def has_perms(self, perm_list, obj=None):
        return False


class GlobalToken(object):
    is_global_token = True
