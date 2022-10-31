import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated
from codecov_auth.models import Session, UserToken
from codecov_auth.tests.factories import OwnerFactory, SessionFactory, UserTokenFactory

from ..revoke_user_token import RevokeUserTokenInteractor


@sync_to_async
def get_user_token(external_id):
    return UserToken.objects.get(external_id=external_id)


class RevokeUserTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.user_token = UserTokenFactory(owner=self.user)

    async def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            await RevokeUserTokenInteractor(AnonymousUser(), "github").execute(123)

    async def test_revoke_user_token(self):
        await RevokeUserTokenInteractor(self.user, "github").execute(
            self.user_token.external_id
        )
        with pytest.raises(UserToken.DoesNotExist):
            await get_user_token(self.user_token.external_id)
