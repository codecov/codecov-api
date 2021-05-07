from .base import BaseCommand

from codecov_auth.models import Owner, Session
from .owner_interactors.create_api_token import CreateApiTokenInteractor
from .owner_interactors.delete_session import DeleteSessionInteractor


class OwnerCommands(BaseCommand):
    def create_api_token(self, name):
        return CreateApiTokenInteractor(self.current_user).execute(name)

    def delete_session(self, sessionid):
        return DeleteSessionInteractor(self.current_user).execute(sessionid)
