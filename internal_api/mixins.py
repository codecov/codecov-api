from rest_framework.exceptions import NotFound

from codecov_auth.models import Owner
from django.core.exceptions import ObjectDoesNotExist
from core.models import Repository, Commit, Branch


class RepoSlugUrlMixin(object):

    def get_repo(self):
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        try:
            owner = Owner.objects.get(service=self.request.user.service, username=org_name)
            return Repository.objects.get(name=repo_name, author=owner)
        except ObjectDoesNotExist:
            raise NotFound(detail="Repository {} for org {} not found ".format(repo_name, org_name))


def get_commit(commit_or_branch, repo):
    """
    :param commit_or_branch: a 40 character sha or branch name
    :param repo: core.models.Repository
    :return: core.models.Commit
    """
    # carrying over logic from:
    # https://github.com/codecov/codecov.io/blob/master/src/sql/main/functions/get_commit.sql#L20-L23
    if len(commit_or_branch) == 40:
        try:
            return Commit.objects.get(repository_id=repo.repoid,commitid=commit_or_branch)
        except ObjectDoesNotExist:
            raise NotFound(detail="Corresponding commit not found for: {}".format(commit_or_branch))
    else:
        try:
            branch = Branch.objects.get(repository=repo, name=commit_or_branch)
            return branch.head
        except ObjectDoesNotExist:
            raise NotFound(detail="Corresponding commit not found for: {}".format(commit_or_branch))


class CompareSlugMixin(RepoSlugUrlMixin):

    def get_commits(self):
        base = self.kwargs.get('base')
        head = self.kwargs.get('head')
        repo = self.get_repo()
        try:
            base = get_commit(base, repo=repo)
            head = get_commit(head, repo=repo)
        except ObjectDoesNotExist:
            raise NotFound(detail="Corresponding commit not found ")
        return base, head



class RepoFilterMixin(RepoSlugUrlMixin):
    """ Repository filter for commits/branches/pulls that uses the args:
        orgName, repoName, and permissions of the authenticated user """

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        repo = self.get_repo()

        # TODO: Verify the user has permissions by calling Provider (and update db)
        # 1. handle logic based on if the repo is public or private
        # 2. handle if it's delayed auth
        # 2. check logic on handling activated repos or if enterprise
        # https://github.com/codecov/codecov.io/blob/master/app/handlers/base.py#L648-L753
        return queryset.filter(repository=repo)
