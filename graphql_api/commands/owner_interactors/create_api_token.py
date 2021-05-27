from asgiref.sync import sync_to_async

from codecov_auth.models import Session
from graphql_api.commands.base import BaseInteractor
from graphql_api.commands.exceptions import Unauthenticated


class CreateApiTokenInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def create_token(self, name):
        type = Session.SessionType.API
        return Session.objects.create(name=name, owner=self.current_user, type=type)

    @sync_to_async
    def execute(self, name):
        self.validate()
        return self.create_token(name)
