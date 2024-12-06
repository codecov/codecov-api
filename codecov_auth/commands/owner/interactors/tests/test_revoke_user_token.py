import pytest
from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    OwnerFactory,
    UserTokenFactory,
)

from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import UserToken

from ..revoke_user_token import RevokeUserTokenInteractor


@sync_to_async
def get_user_token(external_id):
    return UserToken.objects.get(external_id=external_id)


class RevokeUserTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.user_token = UserTokenFactory(owner=self.owner)

    async def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            await RevokeUserTokenInteractor(None, "github").execute(123)

    async def test_revoke_user_token(self):
        await RevokeUserTokenInteractor(self.owner, "github").execute(
            self.user_token.external_id
        )
        with pytest.raises(UserToken.DoesNotExist):
            await get_user_token(self.user_token.external_id)
