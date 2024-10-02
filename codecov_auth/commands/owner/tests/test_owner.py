from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from ..owner import OwnerCommands


class OwnerCommandsTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.command = OwnerCommands(self.owner, "github")

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

    @patch("codecov_auth.commands.owner.owner.CreateUserTokenInteractor.execute")
    def test_create_user_token_delegate_to_interactor(self, interactor_mock):
        name = "new api token"
        self.command.create_user_token(name)
        interactor_mock.assert_called_once_with(name, None)

    @patch("codecov_auth.commands.owner.owner.RevokeUserTokenInteractor.execute")
    def test_revoke_user_token_delegate_to_interactor(self, interactor_mock):
        tokenid = 123
        self.command.revoke_user_token(tokenid)
        interactor_mock.assert_called_once_with(tokenid)

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

    @patch("codecov_auth.commands.owner.owner.SaveTermsAgreementInteractor.execute")
    def test_save_terms_agreement_delegate_to_interactor(self, interactor_mock):
        input_dict = {"email": "a@a.com", "termsAgreement": False}
        self.command.save_terms_agreement(input_dict)
        interactor_mock.assert_called_once_with(input_dict)

    @patch("codecov_auth.commands.owner.owner.StartTrialInteractor.execute")
    def test_start_trial_delegate_to_interactor(self, interactor_mock):
        org_username = "random_org"
        self.command.start_trial(org_username=org_username)
        interactor_mock.assert_called_once_with(org_username=org_username)

    @patch("codecov_auth.commands.owner.owner.CancelTrialInteractor.execute")
    def test_cancel_trial_delegate_to_interactor(self, interactor_mock):
        org_username = "random_org"
        self.command.cancel_trial(org_username=org_username)
        interactor_mock.assert_called_once_with(org_username=org_username)

    @patch(
        "codecov_auth.commands.owner.owner.UpdateDefaultOrganizationInteractor.execute"
    )
    def test_update_default_organization_delegate_to_interactor(self, interactor_mock):
        username = "codecov-user"
        self.command.update_default_organization(default_org_username=username)
        interactor_mock.assert_called_once_with(default_org_username=username)

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

    @patch(
        "codecov_auth.commands.owner.owner.GetIsCurrentUserAnAdminInteractor.execute"
    )
    def test_get_is_current_user_an_admin_delegate_to_interactor(self, interactor_mock):
        owner = {}
        current_user = {}
        self.command.get_is_current_user_an_admin(owner, current_user)
        interactor_mock.assert_called_once_with(owner, current_user)

    @patch("codecov_auth.commands.owner.owner.GetOrgUploadToken.execute")
    def test_get_org_upload_token_delegate_to_interactor(self, interactor_mock):
        owner = {}
        self.command.get_org_upload_token(owner)
        interactor_mock.assert_called_once_with(owner)

    @patch(
        "codecov_auth.commands.owner.owner.RegenerateOrgUploadTokenInteractor.execute"
    )
    def test_regenerate_org_upload_token_delegate_to_interactor(self, interactor_mock):
        owner = {}
        self.command.regenerate_org_upload_token(owner)
        interactor_mock.assert_called_once_with(owner)

    @patch("codecov_auth.commands.owner.owner.SaveOktaConfigInteractor.execute")
    def test_save_okta_config_delegate_to_interactor(self, interactor_mock):
        input_dict = {
            "client_id": "123",
            "client_secret": "123",
            "url": "http://example.com",
            "enabled": True,
            "enforced": False,
            "org_username": "codecov-user",
        }
        self.command.save_okta_config(input_dict)
        interactor_mock.assert_called_once_with(input_dict)

    @patch("codecov_auth.commands.owner.owner.SetUploadTokenRequiredInteractor.execute")
    def test_set_upload_token_required_delegate_to_interactor(self, interactor_mock):
        input_dict = {
            "upload_token_required": True,
            "org_username": "codecov-user",
        }
        self.command.set_upload_token_required(input_dict)
        interactor_mock.assert_called_once_with(input_dict)
