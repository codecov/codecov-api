import asyncio

from rest_framework.exceptions import NotFound, PermissionDenied

from codecov_auth.models import Owner
from django.core.exceptions import ObjectDoesNotExist
from core.models import Repository
from internal_api.repo.repository_accessors import RepoAccessors


class RepoSlugUrlMixin(object):

    def get_repo(self):
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        try:
            owner = Owner.objects.get(service=self.request.user.service, username=org_name)
            return Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            raise NotFound(detail="Repository {} for org {} not found ".format(repo_name, org_name))


class RepoFilterMixin(RepoSlugUrlMixin):
    """ Repository filter for commits/branches/pulls that uses the args:
        orgName, repoName, and permissions of the authenticated user """

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        repo = self.get_repo()

        if repo.private:
            can_view, can_edit = RepoAccessors().get_repo_permissions(self.request.user, repo.name, repo.author.username)
            if not can_view:
                raise PermissionDenied(detail="Do not have permissions to view this repo")
        # TODO:
        # 1. handle if it's delayed auth
        # 2. check logic on handling activated repos or if enterprise
        # https://github.com/codecov/codecov.io/blob/master/app/handlers/base.py#L648-L753
        return queryset.filter(repository=repo)
