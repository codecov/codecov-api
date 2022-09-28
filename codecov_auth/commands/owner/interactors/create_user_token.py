from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import UserToken


class CreateUserTokenInteractor(BaseInteractor):
    def validate(self, name: str, token_type: str):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if len(name) == 0:
            raise ValidationError("name cant be empty")
        if token_type not in UserToken.TokenType.values:
            raise ValidationError(f"invalid token type: {token_type}")

    def create_token(self, name: str, token_type: str) -> UserToken:
        return UserToken.objects.create(
            name=name,
            owner=self.current_user,
            token_type=token_type,
        )

    @sync_to_async
    def execute(self, name: str, token_type: str = None) -> UserToken:
        if token_type is None:
            token_type = UserToken.TokenType.API.value

        self.validate(name, token_type)
        return self.create_token(name, token_type)
