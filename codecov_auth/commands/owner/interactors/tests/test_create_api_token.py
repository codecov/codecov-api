import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError

from ..create_api_token import CreateApiTokenInteractor


class CreateApiTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await CreateApiTokenInteractor(None, "github").execute("name")

    async def test_when_no_name_raise(self):
        with pytest.raises(ValidationError):
            await CreateApiTokenInteractor(self.owner, "github").execute("")

    async def test_create_token(self):
        session = await CreateApiTokenInteractor(self.owner, "github").execute("name")
        assert session is not None
        assert session.owner is self.owner
