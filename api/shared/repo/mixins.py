import logging

from django.http import Http404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS  # ['GET', 'HEAD', 'OPTIONS']

from api.shared.mixins import OwnerPropertyMixin
from api.shared.permissions import RepositoryPermissionsService, UserIsAdminPermissions
from core.models import Repository
from services.decorators import torngit_safe

from .repository_accessors import RepoAccessors

log = logging.getLogger(__name__)


class RepositoryViewSetMixin(
    OwnerPropertyMixin,
    viewsets.GenericViewSet,
):
    lookup_value_regex = "[\w\.@\:\-~]+"
    lookup_field = "repo_name"
    accessors = RepoAccessors()

    def _assert_is_admin(self):
        admin_permissions = UserIsAdminPermissions()
        if not admin_permissions.has_permission(self.request, self):
            raise PermissionDenied()

    def get_queryset(self):
        return (
            Repository.objects.filter(author=self.owner)
            .viewable_repos(self.request.user)
            .select_related("author")
        )

    @torngit_safe
    def check_object_permissions(self, request, repo):
        # Below is some hacking to avoid requesting permissions from API in certain scenarios.
        if not request.user.is_authenticated and not repo.private:
            # Unauthenticated users only have read-access to public repositories,
            # so we avoid this API call here
            self.can_view, self.can_edit = True, False
        elif not request.user.is_authenticated and repo.private:
            raise Http404()
        else:
            # If the user is authenticated, we can fetch permissions from the provider
            # to determine write permissions.
            self.can_view, self.can_edit = self.accessors.get_repo_permissions(
                self.request.user, repo
            )

        if repo.private and not RepositoryPermissionsService().user_is_activated(
            self.request.user, self.owner
        ):
            log.info(
                "An inactive user attempted to access a repo page",
                extra=dict(
                    user=self.request.user.username,
                    owner=self.owner.username,
                    repo=repo.name,
                ),
            )
            raise PermissionDenied("User not activated")
        if self.request.method not in SAFE_METHODS and not self.can_edit:
            raise PermissionDenied()
        if self.request.method == "DELETE":
            self._assert_is_admin()
        if not self.can_view:
            raise Http404()

    @torngit_safe
    def get_object(self):
        # Get request args and try to find the repo in the DB
        repo_name = self.kwargs.get("repo_name")
        org_name = self.kwargs.get("owner_username")
        service = self.kwargs.get("service")

        repo = self.accessors.get_repo_details(
            user=self.request.user,
            repo_name=repo_name,
            repo_owner_username=org_name,
            repo_owner_service=service,
        )

        if repo is None:
            repo = self.accessors.fetch_from_git_and_create_repo(
                user=self.request.user,
                repo_name=repo_name,
                repo_owner_username=org_name,
                repo_owner_service=service,
            )

        self.check_object_permissions(self.request, repo)
        return repo
