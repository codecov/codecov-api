from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Session


class CreateApiTokenInteractor(BaseInteractor):
    def validate(self, name):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if len(name) == 0:
            raise ValidationError("name cant be empty")

    def create_token(self, name):
        type = Session.SessionType.API
        return Session.objects.create(name=name, owner=self.current_user, type=type)

    @sync_to_async
    def execute(self, name):
        self.validate(name)
        return self.create_token(name)
