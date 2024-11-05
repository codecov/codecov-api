from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from ..pull import PullCommands


class PullCommandsTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.command = PullCommands(self.owner, "github")

    @patch("core.commands.pull.pull.FetchPullRequestsInteractor.execute")
    def test_fetch_pull_requests_delegate_to_interactor(self, interactor_mock):
        self.filters = None
        repo = RepositoryFactory()
        self.command.fetch_pull_requests(repo, self.filters)
        interactor_mock.assert_called_once_with(repo, self.filters)

    @patch("core.commands.pull.pull.FetchPullRequestInteractor.execute")
    def test_fetch_pull_request_delegate_to_interactor(self, interactor_mock):
        repo = RepositoryFactory()
        self.command.fetch_pull_request(repo, 12)
        interactor_mock.assert_called_once_with(repo, 12)
