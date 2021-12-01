from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from core.tests.factories import CommitFactory
from reports.tests.factories import CommitReportFactory, ReportLevelTotalsFactory

from ..change_with_parent import ChangeWithParentInteractor


class ChangeWithParentInteractorTest(TransactionTestCase):
    def setUp(self):
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.report = CommitReportFactory(commit=self.commit)
        self.report_totals = ReportLevelTotalsFactory(
            report=self.report, coverage=79.38
        )
        self.report_for_parent = CommitReportFactory(commit=self.parent_commit)
        self.report_totals_for_parent = ReportLevelTotalsFactory(
            report=self.report_for_parent, coverage=63.32
        )

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return ChangeWithParentInteractor(current_user, service).execute(*args)

    def test_change_with_parent_with_coverage(self):
        change = async_to_sync(self.execute)(
            None, self.report_totals, self.report_totals_for_parent
        )
        assert change == 16.059999999999995

    def test_change_with_parent_without_coverage(self):
        change = async_to_sync(self.execute)(None, self.report_totals, None)
        assert change is None
