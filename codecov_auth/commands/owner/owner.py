from codecov.commands.base import BaseCommand

from .interactors.cancel_trial import CancelTrialInteractor
from .interactors.create_api_token import CreateApiTokenInteractor
from .interactors.create_stripe_setup_intent import CreateStripeSetupIntentInteractor
from .interactors.create_user_token import CreateUserTokenInteractor
from .interactors.delete_session import DeleteSessionInteractor
from .interactors.fetch_owner import FetchOwnerInteractor
from .interactors.get_is_current_user_an_admin import GetIsCurrentUserAnAdminInteractor
from .interactors.get_org_upload_token import GetOrgUploadToken
from .interactors.get_uploads_number_per_user import GetUploadsNumberPerUserInteractor
from .interactors.is_syncing import IsSyncingInteractor
from .interactors.onboard_user import OnboardUserInteractor
from .interactors.regenerate_org_upload_token import RegenerateOrgUploadTokenInteractor
from .interactors.revoke_user_token import RevokeUserTokenInteractor
from .interactors.save_okta_config import SaveOktaConfigInteractor
from .interactors.save_terms_agreement import SaveTermsAgreementInteractor
from .interactors.set_upload_token_required import SetUploadTokenRequiredInteractor
from .interactors.set_yaml_on_owner import SetYamlOnOwnerInteractor
from .interactors.start_trial import StartTrialInteractor
from .interactors.store_codecov_metric import StoreCodecovMetricInteractor
from .interactors.trigger_sync import TriggerSyncInteractor
from .interactors.update_default_organization import UpdateDefaultOrganizationInteractor
from .interactors.update_profile import UpdateProfileInteractor
from .interactors.update_self_hosted_settings import UpdateSelfHostedSettingsInteractor


class OwnerCommands(BaseCommand):
    def create_api_token(self, name):
        return self.get_interactor(CreateApiTokenInteractor).execute(name)

    def create_stripe_setup_intent(self, owner):
        return self.get_interactor(CreateStripeSetupIntentInteractor).execute(owner)

    def delete_session(self, sessionid: int):
        return self.get_interactor(DeleteSessionInteractor).execute(sessionid)

    def create_user_token(self, name, token_type=None):
        return self.get_interactor(CreateUserTokenInteractor).execute(name, token_type)

    def revoke_user_token(self, tokenid):
        return self.get_interactor(RevokeUserTokenInteractor).execute(tokenid)

    def set_yaml_on_owner(self, username, yaml):
        return self.get_interactor(SetYamlOnOwnerInteractor).execute(username, yaml)

    def update_profile(self, **kwargs):
        return self.get_interactor(UpdateProfileInteractor).execute(**kwargs)

    def save_terms_agreement(self, input):
        return self.get_interactor(SaveTermsAgreementInteractor).execute(input)

    def update_default_organization(self, **kwargs):
        return self.get_interactor(UpdateDefaultOrganizationInteractor).execute(
            **kwargs
        )

    def fetch_owner(self, username):
        return self.get_interactor(FetchOwnerInteractor).execute(username)

    def trigger_sync(self):
        return self.get_interactor(TriggerSyncInteractor).execute()

    def is_syncing(self):
        return self.get_interactor(IsSyncingInteractor).execute()

    def onboard_user(self, params):
        return self.get_interactor(OnboardUserInteractor).execute(params)

    def get_uploads_number_per_user(self, owner):
        return self.get_interactor(GetUploadsNumberPerUserInteractor).execute(owner)

    def get_is_current_user_an_admin(self, owner, current_user):
        return self.get_interactor(GetIsCurrentUserAnAdminInteractor).execute(
            owner, current_user
        )

    def get_org_upload_token(self, owner):
        return self.get_interactor(GetOrgUploadToken).execute(owner)

    def regenerate_org_upload_token(self, owner):
        return self.get_interactor(RegenerateOrgUploadTokenInteractor).execute(owner)

    def start_trial(self, org_username: str) -> None:
        return self.get_interactor(StartTrialInteractor).execute(
            org_username=org_username
        )

    def cancel_trial(self, org_username: str) -> None:
        return self.get_interactor(CancelTrialInteractor).execute(
            org_username=org_username
        )

    def update_self_hosted_settings(self, input) -> None:
        return self.get_interactor(UpdateSelfHostedSettingsInteractor).execute(input)

    def store_codecov_metric(
        self, org_username: str, event: str, json_string: str
    ) -> None:
        return self.get_interactor(StoreCodecovMetricInteractor).execute(
            org_username, event, json_string
        )

    def save_okta_config(self, input) -> None:
        return self.get_interactor(SaveOktaConfigInteractor).execute(input)

    def set_upload_token_required(self, input) -> None:
        return self.get_interactor(SetUploadTokenRequiredInteractor).execute(input)
