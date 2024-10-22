from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from ..branch import BranchCommands


class BranchCommandsTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.command = BranchCommands(self.owner, "github")

    @patch("core.commands.branch.branch.FetchBranchInteractor.execute")
    def test_fetch_branch_delegate_to_interactor(self, interactor_mock):
        branch_name = "main"
        self.command.fetch_branch(self.repository, branch_name)
        interactor_mock.assert_called_once_with(self.repository, branch_name)

    @patch("core.commands.branch.branch.FetchRepoBranchesInteractor.execute")
    def test_fetch_branches_delegate_to_interactor(self, interactor_mock):
        filters = {}
        self.command.fetch_branches(self.repository, filters)
        interactor_mock.assert_called_once_with(self.repository, filters)
