from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..branch import BranchCommands


class BranchCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.command = BranchCommands(self.user, "github")

    @patch("core.commands.branch.branch.FetchBranchInteractor.execute")
    def test_fetch_branch_delegate_to_interactor(self, interactor_mock):
        branch_name = "main"
        self.command.fetch_branch(self.repository, branch_name)
        interactor_mock.assert_called_once_with(self.repository, branch_name)

    @patch("core.commands.branch.branch.FetchRepoBranchesInteractor.execute")
    def test_fetch_branches_delegate_to_interactor(self, interactor_mock):
        self.command.fetch_branches(self.repository)
        interactor_mock.assert_called_once_with(self.repository)
