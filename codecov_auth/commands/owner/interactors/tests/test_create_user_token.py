import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import UserToken

from ..create_user_token import CreateUserTokenInteractor


class CreateUserTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    async def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            await CreateUserTokenInteractor(None, "github").execute("name")

    async def test_empty_name(self):
        with pytest.raises(ValidationError):
            await CreateUserTokenInteractor(self.owner, "github").execute("")

    async def test_invalid_type(self):
        with pytest.raises(ValidationError):
            await CreateUserTokenInteractor(self.owner, "github").execute(
                "name", "wrong"
            )

    async def test_create_token(self):
        user_token = await CreateUserTokenInteractor(self.owner, "github").execute(
            "name"
        )
        assert user_token is not None
        assert user_token.owner is self.owner
        assert user_token.token_type == UserToken.TokenType.API
