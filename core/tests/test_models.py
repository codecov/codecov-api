from django.forms import ValidationError
from django.test import TestCase

from reports.tests.factories import CommitReportFactory

from .factories import CommitFactory, RepositoryFactory


class RepoTests(TestCase):
    def test_clean_repo(self):
        repo = RepositoryFactory(using_integration=None)
        with self.assertRaises(ValidationError):
            repo.clean()


class CommitTests(TestCase):
    def test_commitreport_no_code(self):
        commit = CommitFactory()
        report1 = CommitReportFactory(
            commit=commit, code="testing"
        )  # this is a report for a "local upload"
        report2 = CommitReportFactory(commit=commit, code=None)
        assert commit.commitreport == report2
