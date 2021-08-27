from asgiref.sync import async_to_sync
import pytest
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory

from ..get_commit_report import GetCommitReportInteractor


class MockLines(object):
    def __init__(self):
        self.lines = []


class MockReport(object):
    def get(self):
        return MockLines()


class GetCommitReportInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetCommitReportInteractor(current_user, service).execute(*args)

    @patch(
        "core.commands.commit.interactors.get_commit_report.ReportService.build_report_from_commit"
    )
    @async_to_sync
    async def test_when_path_has_coverage(self, build_report_from_commit_mock):
        build_report_from_commit_mock.return_value = MockReport
        report = await self.execute(None, self.commit)
        assert MockReport
