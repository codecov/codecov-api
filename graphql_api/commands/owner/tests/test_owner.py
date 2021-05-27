from django.test import TransactionTestCase
from unittest.mock import patch

from codecov_auth.tests.factories import OwnerFactory
from ..owner import OwnerCommands


class OwnerCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.command = OwnerCommands(self.user)

    @patch("graphql_api.commands.owner.owner.CreateApiTokenInteractor.execute")
    def test_create_api_token_delegate_to_interactor(self, interactor_mock):
        name = "new api token"
        self.command.create_api_token(name)
        interactor_mock.assert_called_once_with(name)

    @patch("graphql_api.commands.owner.owner.DeleteSessionInteractor.execute")
    def test_delete_session_delegate_to_interactor(self, interactor_mock):
        sessionid = 12
        self.command.delete_session(sessionid)
        interactor_mock.assert_called_once_with(sessionid)
