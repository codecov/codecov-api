import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Session
from codecov_auth.tests.factories import OwnerFactory

from ..create_api_token import CreateApiTokenInteractor


class CreateApiTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await CreateApiTokenInteractor(AnonymousUser(), "github").execute("name")

    async def test_when_no_name_raise(self):
        with pytest.raises(ValidationError):
            await CreateApiTokenInteractor(self.user, "github").execute("")

    async def test_create_token(self):
        session = await CreateApiTokenInteractor(self.user, "github").execute("name")
        assert session is not None
        assert session.owner is self.user
