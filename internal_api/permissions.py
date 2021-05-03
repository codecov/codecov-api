import logging
import asyncio
from django.http import Http404

from rest_framework.permissions import BasePermission
from rest_framework.permissions import SAFE_METHODS  # ['GET', 'HEAD', 'OPTIONS']

from services.decorators import torngit_safe
from services.segment import SegmentService
from services.repo_providers import get_generic_adapter_params, get_provider
from internal_api.repo.repository_accessors import RepoAccessors


log = logging.getLogger(__name__)


class RepositoryPermissionsService:
    @torngit_safe
    def _fetch_provider_permissions(self, user, repo):
        can_view, can_edit = RepoAccessors().get_repo_permissions(user, repo)

        if can_view:
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

    def user_is_activated(self, user, owner):
        if user.ownerid == owner.ownerid:
            return True
        if owner.has_legacy_plan:
            return True
        if user.organizations is None or owner.ownerid not in user.organizations:
            return False
        if owner.plan_activated_users and user.ownerid in owner.plan_activated_users:
            return True
        if owner.plan_auto_activate:
            log.info(
                f"Attemping to auto-activate user {user.ownerid} in {owner.ownerid}"
            )
            if owner.can_activate_user(user):
                owner.activate_user(user)
                SegmentService().account_activated_user(
                    current_user_ownerid=user.ownerid,
                    ownerid_to_activate=user.ownerid,
                    org_ownerid=owner.ownerid,
                    auto_activated=True,
                )
                return True
            else:
                log.info("Auto-activation failed -- not enough seats remaining")

        return False


class RepositoryArtifactPermissions(BasePermission):
    """
    Permissions class for artifacts of a repository, eg commits, branches,
    pulls, comparisons, etc. Requires that the view has a '.repo'
    property that returns the repo being worked on.
    """

    permissions_service = RepositoryPermissionsService()
    message = (
        f"Permission denied: some possbile reasons for this are (1) the "
        f"user doesn't have permission to view the specific resource; "
        f"or (2) the organization has a per-user plan, and the user is "
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


class ChartPermissions(BasePermission):
    permissions_service = RepositoryPermissionsService()

    def has_permission(self, request, view):
        for repo in view.repositories:
            # TODO: this can cause a provider-api request for every repo in the list,
            # can we just rely on our stored read permissions? In fact, it seems like
            # permissioning is built into internal_api.charts.filter.add_simple_filters
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

        return asyncio.run(
            torngit_provider_adapter.get_is_admin(
                user={"username": user.username, "service_id": user.service_id}
            )
        )
