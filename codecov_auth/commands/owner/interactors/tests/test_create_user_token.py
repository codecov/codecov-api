import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.models import UserToken
from codecov_auth.tests.factories import OwnerFactory

from ..create_user_token import CreateUserTokenInteractor


class CreateUserTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    async def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            await CreateUserTokenInteractor(AnonymousUser(), "github").execute("name")

    async def test_empty_name(self):
        with pytest.raises(ValidationError):
            await CreateUserTokenInteractor(self.user, "github").execute("")

    async def test_invalid_type(self):
        with pytest.raises(ValidationError):
            await CreateUserTokenInteractor(self.user, "github").execute(
                "name", "wrong"
            )

    async def test_invalid_global_token(self):
        with pytest.raises(ValidationError):
            await CreateUserTokenInteractor(self.user, "github").execute(
                "name", "g_api"
            )

    async def test_create_token(self):
        user_token = await CreateUserTokenInteractor(self.user, "github").execute(
            "name"
        )
        assert user_token is not None
        assert user_token.owner is self.user
        assert user_token.token_type == UserToken.TokenType.API
