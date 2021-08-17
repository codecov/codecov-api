from uuid import UUID

from core.models import Repository

from rest_framework import authentication
from rest_framework.permissions import BasePermission

from upload.authentication.types import RepositoryAsUser, RepositoryAuth, AuthSource


class RepositoryLegacyTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = request.GET.get("token")
        if not token:
            return None
        try:
            token = UUID(token)
        except ValueError:
            return None
        try:
            repository = Repository.objects.get(upload_token=token)
        except Repository.DoesNotExist:
            return None
        return (
            RepositoryAsUser(repository),
            RepositoryAuth(repository, AuthSource.legacy_token, {"token": token}),
        )


class RepositoryHasScopePermission(BasePermission):

    def has_permission(self, request, view):
        if not isinstance(request.auth, RepositoryAuth):
            return False
        if set(view.required_repositories) - set(request.auth.get_repositories()):
            return False
        if set(view.required_scopes) - set(request.auth.get_scopes()):
            return False
        return True
