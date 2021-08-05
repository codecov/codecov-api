from asgiref.sync import async_to_sync
import asyncio
import pytest
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
from shared.torngit.exceptions import TorngitObjectNotFoundError
from services.archive import SerializableReport, build_report
from ..get_file_coverage import GetFileCoverageInteractor


class MockCoverage(object):
    def __init__(self, cov):
        self.coverage = cov


class MockLines(object):
    def __init__(self):
        self.lines = [
            [0, MockCoverage("1/2")],
            [1, MockCoverage(1)],
            [2, MockCoverage(0)],
        ]


class MockReport(object):
    def get(self):
        return MockLines()


class GetFileCoverageInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetFileCoverageInteractor(current_user, service).execute(*args)

    @patch(
        "core.commands.commit.interactors.get_file_coverage.ReportService.build_report_from_commit"
    )
    @async_to_sync
    async def test_when_path_has_coverage(self, build_report_from_commit_mock):
        expected_result = [
            {"line": 0, "coverage": 2},
            {"line": 1, "coverage": 1},
            {"line": 2, "coverage": 0},
        ]
        build_report_from_commit_mock.return_value = MockReport
        file_content = await self.execute(None, self.commit, "awesome/__init__.py")
        assert file_content == expected_result
