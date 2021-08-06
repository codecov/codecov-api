from codecov.commands.base import BaseCommand

from codecov_auth.models import Owner, Session
from .interactors.create_api_token import CreateApiTokenInteractor
from .interactors.set_yaml_on_owner import SetYamlOnOwnerInteractor
from .interactors.delete_session import DeleteSessionInteractor
from .interactors.update_profile import UpdateProfileInteractor
from .interactors.fetch_owner import FetchOwnerInteractor


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
