from rest_framework.exceptions import NotFound

from codecov_auth.models import Owner
from django.core.exceptions import ObjectDoesNotExist
from core.models import Repository


class RepoFilterMixin(object):
    """ Repository filter for commits/branches/pulls that uses the args:
        orgName, repoName, and permissions of the authenticated user """

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        try:
            owner = Owner.objects.get(service=self.request.user.service, username=org_name)
            repo = Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            raise NotFound(detail="Repository {} for org {} not found ".format(repo_name, org_name))

        # TODO: Verify the user has permissions by calling Provider (and update db)
        # 1. handle logic based on if the repo is public or private
        # 2. handle if it's delayed auth
        # 2. check logic on handling activated repos or if enterprise
        # https://github.com/codecov/codecov.io/blob/master/app/handlers/base.py#L648-L753
        return queryset.filter(repository=repo)
