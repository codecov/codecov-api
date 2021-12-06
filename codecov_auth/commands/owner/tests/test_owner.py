from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory

from ..owner import OwnerCommands


class OwnerCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.command = OwnerCommands(self.user, "github")

    @patch("codecov_auth.commands.owner.owner.CreateApiTokenInteractor.execute")
    def test_create_api_token_delegate_to_interactor(self, interactor_mock):
        name = "new api token"
        self.command.create_api_token(name)
        interactor_mock.assert_called_once_with(name)

    @patch("codecov_auth.commands.owner.owner.DeleteSessionInteractor.execute")
    def test_delete_session_delegate_to_interactor(self, interactor_mock):
        sessionid = 12
        self.command.delete_session(sessionid)
        interactor_mock.assert_called_once_with(sessionid)

    @patch("codecov_auth.commands.owner.owner.SetYamlOnOwnerInteractor.execute")
    def test_set_yaml_on_owner_delegate_to_interactor(self, interactor_mock):
        username = "codecov"
        yaml = "codecov: something"
        self.command.set_yaml_on_owner(username, yaml)
        interactor_mock.assert_called_once_with(username, yaml)

    @patch("codecov_auth.commands.owner.owner.UpdateProfileInteractor.execute")
    def test_update_profile_delegate_to_interactor(self, interactor_mock):
        name = "codecov name"
        self.command.update_profile(name=name)
        interactor_mock.assert_called_once_with(name=name)

    @patch("codecov_auth.commands.owner.owner.TriggerSyncInteractor.execute")
    def test_trigger_sync_delegate_to_interactor(self, interactor_mock):
        self.command.trigger_sync()
        interactor_mock.assert_called_once()

    @patch("codecov_auth.commands.owner.owner.IsSyncingInteractor.execute")
    def test_is_syncing_delegate_to_interactor(self, interactor_mock):
        self.command.is_syncing()
        interactor_mock.assert_called_once()

    @patch("codecov_auth.commands.owner.owner.OnboardUserInteractor.execute")
    def test_onboard_user_delegate_to_interactor(self, interactor_mock):
        params = {}
        self.command.onboard_user(params)
        interactor_mock.assert_called_once_with(params)

    @patch(
        "codecov_auth.commands.owner.owner.GetUploadsNumberPerUserInteractor.execute"
    )
    def test_get_uploads_number_per_user_delegate_to_interactor(self, interactor_mock):
        owner = {}
        self.command.get_uploads_number_per_user(owner)
        interactor_mock.assert_called_once_with(owner)
