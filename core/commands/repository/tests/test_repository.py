from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from ..repository import RepositoryCommands


class RepositoryCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = AnonymousUser()
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org)
        self.command = RepositoryCommands(None, "github")

    @patch("core.commands.repository.repository.FetchRepositoryInteractor.execute")
    def test_fetch_repository_to_interactor(self, interactor_mock):
        self.command.fetch_repository(self.org, self.repo.name, [])
        interactor_mock.assert_called_once_with(
            self.org, self.repo.name, [], exclude_okta_enforced_repos=True
        )

    @patch("core.commands.repository.repository.FetchRepositoryInteractor.execute")
    def test_fetch_repository_to_interactor_with_enforcing_okta(self, interactor_mock):
        self.command.fetch_repository(
            self.org, self.repo.name, [], exclude_okta_enforced_repos=False
        )
        interactor_mock.assert_called_once_with(
            self.org, self.repo.name, [], exclude_okta_enforced_repos=False
        )

    @patch("core.commands.repository.repository.GetUploadTokenInteractor.execute")
    def test_get_upload_token_to_interactor(self, interactor_mock):
        self.command.get_upload_token(self.repo)
        interactor_mock.assert_called_once_with(self.repo)
