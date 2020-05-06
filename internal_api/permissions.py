import asyncio

from rest_framework.permissions import BasePermission
from rest_framework.permissions import SAFE_METHODS # ['GET', 'HEAD', 'OPTIONS']

from services.repo_providers import RepoProviderService
from services.decorators import torngit_safe
from internal_api.repo.repository_accessors import RepoAccessors


class RepositoryPermissionsService:
    @torngit_safe
    def _fetch_provider_permissions(self, user, repo):
        can_view, can_edit = RepoAccessors().get_repo_permissions(user, repo)

        if can_view:
            user.permission.append(repo.repoid)
            user.save(update_fields=['permission'])

        return can_view, can_edit

    def has_read_permissions(self, user, repo):
        return (
            repo.author.ownerid == user.ownerid
            or repo.repoid in user.permission
            or not repo.private
            or self._fetch_provider_permissions(user, repo)[0]
        )


class RepositoryArtifactPermissions(BasePermission):
    """
    Permissions class for artifacts of a repository, eg commits, branches,
    pulls, comparisons, etc. Requires that the view has a `'.repo'
    property that returns the repo being worked on.
    """
    permissions_service = RepositoryPermissionsService()

    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS
            and self.permissions_service.has_read_permissions(request.user, view.repo)
        )
