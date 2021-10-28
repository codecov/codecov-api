from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..repository import RepositoryCommands


class RepositoryCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = AnonymousUser()
        self.owner = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.owner)
        self.command = RepositoryCommands(self.user, "github")

    @patch("core.commands.repository.repository.FetchRepositoryInteractor.execute")
    def test_fetch_repository_to_interactor(self, interactor_mock):
        self.command.fetch_repository(self.owner, self.repo.name)
        interactor_mock.assert_called_once_with(self.owner, self.repo.name)

    @patch("core.commands.repository.repository.GetUploadTokenInteractor.execute")
    def test_get_upload_token_to_interactor(self, interactor_mock):
        self.command.get_upload_token(self.repo)
        interactor_mock.assert_called_once_with(self.repo)
