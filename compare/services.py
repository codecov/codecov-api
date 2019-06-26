import asyncio

from archive.services import ReportService
from repo_providers.services import RepoProviderService


def get_comparison_from_pull_request(pull_request):
    # TODO (build)
    pass


class Comparison(object):

    def __init__(self, base_commit, head_commit):
        self.base_commit = base_commit
        self.head_commit = head_commit
        self.report_service = ReportService()

    @property
    def git_diff(self):
        if self._git_diff is None:
            self._git_diff = self._calculate_git_diff()
        return self._git_diff

    def _calculate_git_diff(self):
        loop = asyncio.get_event_loop()
        user = self.context.get("user")
        base_commit_sha = self.base_commit.commitid
        head_commit_sha = self.head_commit.commitid
        task = RepoProviderService().get_adapter(
            user, self.base_commit.repository).get_commit_diff(base_commit_sha, head_commit_sha)
        return loop.run_until_complete(task)

    def base_report(self):
        return self.report_service.build_report_from_commit(self.base_commit)

    def head_report(self):
        return self.report_service.build_report_from_commit(self.head_commit)
