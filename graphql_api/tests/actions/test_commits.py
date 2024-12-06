from collections import Counter

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from graphql_api.actions.commits import repo_commits
from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory, UploadFactory


class RepoCommitsTests(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.repo_with_deleted_commits = RepositoryFactory(
            author=self.org, private=False
        )
        self.commits = [
            CommitFactory(repository=self.repo, message="Foo Bar", state="complete"),
            CommitFactory(
                repository=self.repo, branch="test", message="barn", state="error"
            ),
            CommitFactory(
                repository=self.repo, branch="test", message="baz", state="pending"
            ),
        ]
        self.deleted_commits = [
            CommitFactory(repository=self.repo_with_deleted_commits, deleted=True),
            CommitFactory(
                repository=self.repo_with_deleted_commits, branch="test", deleted=True
            ),
            CommitFactory(
                repository=self.repo_with_deleted_commits, branch="test", deleted=True
            ),
        ]
        self.repo_2 = RepositoryFactory(author=self.org, private=False)
        self.commits_2 = [
            CommitFactory(repository=self.repo_2, pullid=179),
            CommitFactory(repository=self.repo_2, branch="test2", pullid=179),
            CommitFactory(repository=self.repo_2, ci_passed=False, branch="test2"),
        ]

    def test_all(self):
        commits = repo_commits(self.repo, None)
        assert len(list(commits)) == 3
        assert Counter(list(commits)) == Counter(self.commits)

    def test_hide_failed_ci(self):
        commits = repo_commits(self.repo_2, {"hide_failed_ci": True})
        commits_with_filter = list(
            filter(lambda commit: commit.ci_passed is True, self.commits_2)
        )
        assert Counter(list(commits)) == Counter(commits_with_filter)

    def test_pullid(self):
        commits = repo_commits(self.repo_2, {"pull_id": 179})
        commits_with_filter = list(
            filter(lambda commit: commit.pullid == 179, self.commits_2)
        )
        assert Counter(list(commits)) == Counter(commits_with_filter)

    def test_branch_name(self):
        commits = repo_commits(self.repo, {"branch_name": "test"})
        commits_with_filter = list(
            filter(lambda commit: commit.branch == "test", self.commits)
        )
        assert Counter(list(commits)) == Counter(commits_with_filter)

    def test_deleted_commits(self):
        commits = repo_commits(self.repo_with_deleted_commits, None)
        assert list(commits) == []

    def test_branch_name_hide_failed_ci(self):
        commits = repo_commits(
            self.repo_2, {"hide_failed_ci": True, "branch_name": "test2"}
        )
        commits_with_filter = list(
            filter(
                lambda commit: commit.branch == "test2" and commit.ci_passed is True,
                self.commits_2,
            )
        )
        assert list(commits) == commits_with_filter

    def test_long_sha(self):
        commits = repo_commits(self.repo, {"search": self.commits[0].commitid})
        assert list(commits) == [self.commits[0]]

    def test_short_sha(self):
        commits = repo_commits(self.repo, {"search": self.commits[0].commitid[0:7]})
        assert list(commits) == [self.commits[0]]

    def test_message(self):
        commits = repo_commits(self.repo, {"search": "bar"})
        assert list(commits) == [self.commits[0], self.commits[1]]

    def test_states(self):
        commits = repo_commits(self.repo, {"states": ["complete", "pending"]})
        assert list(commits) == [self.commits[0], self.commits[2]]

    def test_coverage_status(self):
        report_0 = CommitReportFactory(
            commit=self.commits[0], report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=report_0, state="processed")
        report_1 = CommitReportFactory(
            commit=self.commits[1], report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=report_1, state="uploaded")
        report_2 = CommitReportFactory(
            commit=self.commits[2], report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=report_2, state="error")

        commits = repo_commits(self.repo, {"coverage_status": ["COMPLETED"]})
        assert list(commits) == [self.commits[0]]

        commits = repo_commits(self.repo, {"coverage_status": ["PENDING"]})
        assert list(commits) == [self.commits[1]]

        commits = repo_commits(self.repo, {"coverage_status": ["ERROR"]})
        assert list(commits) == [self.commits[2]]

        commits = repo_commits(self.repo, {"coverage_status": ["COMPLETED", "PENDING"]})
        assert list(commits) == [self.commits[0], self.commits[1]]

        commits = repo_commits(
            self.repo, {"coverage_status": ["COMPLETED", "PENDING", "ERROR"]}
        )
        assert list(commits) == [self.commits[0], self.commits[1], self.commits[2]]

        commits = repo_commits(self.repo, {"coverage_status": []})
        assert list(commits) == [self.commits[0], self.commits[1], self.commits[2]]
