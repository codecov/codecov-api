import asyncio

from archive.services import ReportService
from repo_providers.services import RepoProviderService


def get_comparison_from_pull_request(pull_request):
    # TODO (build)
    pass


class Comparison(object):

    def __init__(self, base_commit, head_commit, user):
        self.user = user
        self.base_commit = base_commit
        self.head_commit = head_commit
        self.report_service = ReportService()
        self._base_report = None
        self._git_diff = None
        self._head_report = None

    @property
    def git_diff(self):
        if self._git_diff is None:
            self._git_diff = self._calculate_git_diff()
            import pprint
            pprint.pprint(self._git_diff)
        return self._git_diff

    @property
    def base_report(self):
        if self._base_report is None:
            self._base_report = self.report_service.build_report_from_commit(self.base_commit)
        return self._base_report

    @property
    def head_report(self):
        if self._head_report is None:
            self._head_report = self.report_service.build_report_from_commit(self.head_commit)
        return self._head_report

    def _calculate_git_diff(self):
        loop = asyncio.get_event_loop()
        base_commit_sha = self.base_commit.commitid
        head_commit_sha = self.head_commit.commitid
        task = RepoProviderService().get_adapter(
            self.user, self.base_commit.repository).get_compare(base_commit_sha, head_commit_sha)
        return loop.run_until_complete(task)

    def _calculate_base_report(self):
        return self.report_service.build_report_from_commit(self.base_commit)

    def _calculate_head_report(self):
        return self.report_service.build_report_from_commit(self.head_commit)

    def flag_comparison(self, flag_name):
        return FlagComparison(self, flag_name)


class FlagComparison(object):

    def __init__(self, comparison, flag_name):
        self.comparison = comparison
        self.flag_name = flag_name

    @property
    def head_report(self):
        return self.comparison.head_report.flags[self.flag_name]

    @property
    def base_report(self):
        return self.comparison.base_report.flags[self.flag_name]

    @property
    def diff_totals(self):
        git_diff = self.comparison.git_diff
        return self.head_report.apply_diff(git_diff['diff'])
