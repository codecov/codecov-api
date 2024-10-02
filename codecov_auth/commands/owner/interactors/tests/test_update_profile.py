import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError

from ..update_profile import UpdateProfileInteractor


class UpdateProfileInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await UpdateProfileInteractor(None, "github").execute(name="hello")

    async def test_when_email_wrong(self):
        with pytest.raises(ValidationError):
            await UpdateProfileInteractor(self.owner, "github").execute(
                email="not-right"
            )

    async def test_update_name(self):
        user = await UpdateProfileInteractor(self.owner, "github").execute(name="hello")
        assert user.name == "hello"

    async def test_update_email(self):
        user = await UpdateProfileInteractor(self.owner, "github").execute(
            email="hello@codecov.io"
        )
        assert user.email == "hello@codecov.io"

    async def test_update_email_and_name(self):
        user = await UpdateProfileInteractor(self.owner, "github").execute(
            name="codecov brother", email="brother@codecov.io"
        )
        assert user == self.owner
        assert user.email == "brother@codecov.io"
        assert user.name == "codecov brother"
