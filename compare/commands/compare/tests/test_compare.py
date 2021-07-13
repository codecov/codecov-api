from django.test import TransactionTestCase
from unittest.mock import patch
from core.tests.factories import CommitFactory

from codecov_auth.tests.factories import OwnerFactory
from ..compare import CompareCommands


class CompareCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.command = CompareCommands(self.user, "github")

    @patch("compare.commands.compare.compare.CompareCommitsInteractor.execute")
    async def test_compare_commit_when_no_parents(self, interactor_mock):
        commit = CommitFactory()
        compare = await self.command.compare_commit_with_parent(commit)
        assert compare is None
        interactor_mock.assert_not_called()

    @patch("compare.commands.compare.compare.CompareCommitsInteractor.execute")
    async def test_compare_commit_when_parents(self, interactor_mock):
        parent_commit = CommitFactory()
        commit = CommitFactory(
            parent_commit_id=parent_commit.commitid, repository=parent_commit.repository
        )
        compare = await self.command.compare_commit_with_parent(commit)
        assert compare is not None
        interactor_mock.assert_called_with(commit, parent_commit)
