import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import Http404
from rest_framework.permissions import SAFE_METHODS  # ['GET', 'HEAD', 'OPTIONS']
from rest_framework.permissions import BasePermission

import services.self_hosted as self_hosted
from api.shared.mixins import InternalPermissionsMixin, SuperPermissionsMixin
from api.shared.repo.repository_accessors import RepoAccessors
from services.activation import try_auto_activate
from services.decorators import torngit_safe
from services.repo_providers import get_generic_adapter_params, get_provider

log = logging.getLogger(__name__)


class RepositoryPermissionsService:
    @torngit_safe
    def _fetch_provider_permissions(self, user, repo):
        can_view, can_edit = RepoAccessors().get_repo_permissions(user, repo)

        if can_view:
            user.permission = user.permission or []
            user.permission.append(repo.repoid)
            user.save(update_fields=["permission"])

        return can_view, can_edit

    def has_read_permissions(self, user, repo):
        return not repo.private or (
            user.is_authenticated
            and (
                repo.author.ownerid == user.ownerid
                or user.permission
                and repo.repoid in user.permission
                or self._fetch_provider_permissions(user, repo)[0]
            )
        )

    def has_write_permissions(self, user, repo):
        return user.is_authenticated and (
            repo.author.ownerid == user.ownerid
            or self._fetch_provider_permissions(user, repo)[1]
        )

    def user_is_activated(self, user, owner):
        if user.ownerid == owner.ownerid:
            return True
        if owner.has_legacy_plan:
            return True
        if user.organizations is None or owner.ownerid not in user.organizations:
            return False
        if owner.plan_activated_users and user.ownerid in owner.plan_activated_users:
            return True
        return try_auto_activate(owner, user)


class RepositoryArtifactPermissions(BasePermission):
    """
    Permissions class for artifacts of a repository, eg commits, branches,
    pulls, comparisons, etc. Requires that the view has a '.repo'
    property that returns the repo being worked on.
    """

    permissions_service = RepositoryPermissionsService()
    message = (
        f"Permission denied: some possible reasons for this are (1) the "
        f"user doesn't have permission to view the specific resource, "
        f"(2) the organization has a per-user plan or (3) the user is "
        f"trying to view a private repo but is not activated."
    )

    def has_permission(self, request, view):
        if view.repo.private:
            user_activated_permissions = (
                request.user.is_authenticated
                and self.permissions_service.user_is_activated(request.user, view.owner)
            )
        else:
            user_activated_permissions = True
        has_read_permissions = (
            request.method in SAFE_METHODS
            and self.permissions_service.has_read_permissions(request.user, view.repo)
        )
        if has_read_permissions and user_activated_permissions:
            return True
        if has_read_permissions and not user_activated_permissions:
            # user that can access the repo; but are not activated
            return False
        raise Http404()


class SuperTokenPermissions(BasePermission, SuperPermissionsMixin):
    def has_permission(self, request, view):
        return self.has_super_token_permissions(request)


class InternalTokenPermissions(BasePermission, InternalPermissionsMixin):
    def has_permission(self, request, view):
        return self.has_internal_token_permissions(request)


class ChartPermissions(BasePermission):
    permissions_service = RepositoryPermissionsService()

    def has_permission(self, request, view):
        log.info(
            f"Coverage chart has repositories {view.repositories}",
            extra=dict(user=request.user),
        )
        for repo in view.repositories:
            # TODO: this can cause a provider-api request for every repo in the list,
            # can we just rely on our stored read permissions? In fact, it seems like
            # permissioning is built into api.internal.charts.filter.add_simple_filters
            if not self.permissions_service.has_read_permissions(request.user, repo):
                raise Http404
        return True


class UserIsAdminPermissions(BasePermission):
    """
    Permissions class for asserting the user is an admin of the 'owner'
    being queried. Requires that the view has a '.owner' property that
    returns this owner.
    """

    def has_permission(self, request, view):
        if settings.IS_ENTERPRISE:
            return self_hosted.is_admin_owner(request.user)
        return request.user.is_authenticated and (
            view.owner.is_admin(request.user)
            or self._is_admin_on_provider(request.user, view.owner)
        )

    @torngit_safe
    def _is_admin_on_provider(self, user, owner):
        torngit_provider_adapter = get_provider(
            owner.service,
            {
                **get_generic_adapter_params(user, owner.service),
                **{
                    "owner": {
                        "username": owner.username,
                        "service_id": owner.service_id,
                    }
                },
            },
        )

        return async_to_sync(torngit_provider_adapter.get_is_admin)(
            user={"username": user.username, "service_id": user.service_id}
        )


class MemberOfOrgPermissions(BasePermission):
    """
    Permissions class for asserting the user is member of the owner.
    Requires that the view has a '.owner' property that returns this owner.
    """

    def has_permission(self, request, view):
        current_user = request.user
        owner = view.owner
        if not current_user.is_authenticated:
            return False
        if current_user == owner:
            return True
        if owner.ownerid in (current_user.organizations or []):
            return True
        else:
            raise Http404("No Owner matches the given query.")
