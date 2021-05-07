from .base import BaseCommand

from codecov_auth.models import Owner, Session
from .owner_interactors.create_api_token import CreateApiTokenInteractor


class OwnerCommands(BaseCommand):
    def create_api_token(self, name):
        return CreateApiTokenInteractor(self.current_user).execute(name)
