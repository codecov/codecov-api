import asyncio

from archive.services import ReportService
from core.models import Commit
from repo_providers.services import RepoProviderService


def get_comparison_from_pull_request(pull_request, user):
    return Comparison(pull_request.base, pull_request.head, user)


class Comparison(object):

    def __init__(self, base_commit, head_commit, user):
        self.user = user
        self.base_commit = base_commit
        self.head_commit = head_commit
        self.report_service = ReportService()
        self._base_report = None
        self._git_comparison = None
        self._head_report = None
        self._git_commits = None
        self._upload_commits = None

    @property
    def git_comparison(self):
        if self._git_comparison is None:
            self._git_comparison = self._calculate_git_comparison()
        return self._git_comparison

    @property
    def base_report(self):
        if self._base_report is None:
            self._base_report = self._calculate_base_report()
        return self._base_report

    @property
    def head_report(self):
        if self._head_report is None:
            self._head_report = self._calculate_head_report()
        return self._head_report

    @property
    def git_commits(self):
        """
            Returns the complete git commits between base and head.
            :return: list of commit info with objects
        """
        if self._git_commits is None:
            self._calculate_git_commits()
        return self._git_commits

    @property
    def upload_commits(self):
        """
            Returns the commits that have uploads between base and head.
            :return: Queryset of core.models.Commit objects
        """
        commit_ids = [commit['commitid'] for commit in self.git_commits]
        commits_queryset = Commit.objects.filter(commitid__in=commit_ids,
                                                 repository=self.base_commit.repository)
        commits_queryset.exclude(deleted=True)
        return commits_queryset

    def file_diff(self, file_path):
        diff = self.git_comparison['diff']['files']
        if file_path in diff:
            return dict(src_diff=diff[file_path],
                        base_coverage=self.base_report.get(filename=file_path, _else=None),
                        head_coverage=self.head_report.get(filename=file_path, _else=None))

    async def file_source(self, file_path, before_path=None):
        provider = RepoProviderService().get_adapter(self.user, self.base_commit.repository)
        assert file_path in self.head_commit.report['files'], (404, 'File not found on head commit.')
        # get full src at head
        head_source = await provider.get_source(file_path, self.head_commit.commitid)

        if before_path:
            # File name changed in between base & head
            assert before_path in self.base_commit.report['files'], (404, 'File/folder was not found on base commit.')
            base_source = await provider.get_source(before_path, self.base_commit.commitid)
            return dict(sources=dict(base=base_source['content'].splitlines(),
                                     head=head_source['content'].splitlines()))
        else:
            # the file hasn't changed, return head source
            return dict(sources=dict(base=None,
                                     head=head_source['content'].splitlines()))

    def _calculate_git_commits(self):
        commits = self.git_comparison['commits']
        self._git_commits = commits
        return self._git_commits

    def _calculate_git_comparison(self):
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

    @property
    def available_flags(self):
        return self.head_report.flags.keys()


class FlagComparison(object):

    def __init__(self, comparison, flag_name):
        self.comparison = comparison
        self.flag_name = flag_name

    @property
    def head_report(self):
        return self.comparison.head_report.flags.get(self.flag_name)

    @property
    def base_report(self):
        return self.comparison.base_report.flags.get(self.flag_name)

    @property
    def diff_totals(self):
        if self.head_report is None:
            return None
        git_comparison = self.comparison.git_comparison
        return self.head_report.apply_diff(git_comparison['diff'])
