import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OwnerFactory

from ..update_profile import UpdateProfileInteractor


class UpdateProfileInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await UpdateProfileInteractor(AnonymousUser(), "github").execute(
                name="hello"
            )

    async def test_when_email_wrong(self):
        with pytest.raises(ValidationError):
            await UpdateProfileInteractor(self.user, "github").execute(
                email="not-right"
            )

    async def test_update_name(self):
        user = await UpdateProfileInteractor(self.user, "github").execute(name="hello")
        assert user.name == "hello"

    async def test_update_email(self):
        user = await UpdateProfileInteractor(self.user, "github").execute(
            email="hello@codecov.io"
        )
        assert user.email == "hello@codecov.io"

    async def test_update_email_and_name(self):
        user = await UpdateProfileInteractor(self.user, "github").execute(
            name="codecov brother", email="brother@codecov.io"
        )
        assert user.email == "brother@codecov.io"
        assert user.name == "codecov brother"
