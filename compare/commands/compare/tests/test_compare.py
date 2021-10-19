import asyncio
from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, PullFactory

from ..compare import CompareCommands


class CompareCommandsTest(TransactionTestCase):
    def setUp(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.user = OwnerFactory(username="codecov-user")
        self.command = CompareCommands(self.user, "github")

        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
        )
        self.pull = PullFactory(
            repository=self.commit.repository,
            head=self.commit.commitid,
            compared_to=self.parent_commit.commitid,
            pullid=999,
        )

    async def test_compare_commit_when_no_parents(self):
        compare = await self.command.compare_commit_with_parent(self.parent_commit)
        assert compare is None

    async def test_compare_commit_when_parents(self):
        compare = await self.command.compare_commit_with_parent(self.commit)
        assert compare is not None

    async def test_compare_pull_request(self):
        compare = await self.command.compare_pull_request(self.pull)
        assert compare is not None

    @patch("compare.commands.compare.compare.GetImpactedFilesInteractor.execute")
    def test_get_impacted_files_delegrate_to_interactor(self, interactor_mock):
        self.command.get_impacted_files(self.comparison)
        interactor_mock.assert_called_once_with(self.comparison)
