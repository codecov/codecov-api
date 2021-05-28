import pytest
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser

from codecov_auth.models import Session
from codecov_auth.tests.factories import OwnerFactory
from ..create_api_token import CreateApiTokenInteractor
from graphql_api.commands.exceptions import Unauthenticated


class CreateApiTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await CreateApiTokenInteractor(AnonymousUser()).execute("name")

    async def test_create_token(self):
        session = await CreateApiTokenInteractor(self.user).execute("name")
        assert session is not None
        assert session.owner is self.user
