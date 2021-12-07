from codecov.commands.base import BaseCommand
from codecov_auth.models import Owner, Session

from .interactors.create_api_token import CreateApiTokenInteractor
from .interactors.delete_session import DeleteSessionInteractor
from .interactors.fetch_owner import FetchOwnerInteractor
from .interactors.get_uploads_number_per_user import GetUploadsNumberPerUserInteractor
from .interactors.is_syncing import IsSyncingInteractor
from .interactors.onboard_user import OnboardUserInteractor
from .interactors.set_yaml_on_owner import SetYamlOnOwnerInteractor
from .interactors.trigger_sync import TriggerSyncInteractor
from .interactors.update_profile import UpdateProfileInteractor


class OwnerCommands(BaseCommand):
    def create_api_token(self, name):
        return self.get_interactor(CreateApiTokenInteractor).execute(name)

    def delete_session(self, sessionid):
        return self.get_interactor(DeleteSessionInteractor).execute(sessionid)

    def set_yaml_on_owner(self, username, yaml):
        return self.get_interactor(SetYamlOnOwnerInteractor).execute(username, yaml)

    def update_profile(self, **kwargs):
        return self.get_interactor(UpdateProfileInteractor).execute(**kwargs)

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
