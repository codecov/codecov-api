import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import Session
from codecov_auth.tests.factories import OwnerFactory, SessionFactory

from ..delete_session import DeleteSessionInteractor


@sync_to_async
def get_session(id):
    return Session.objects.get(sessionid=id)


class DeleteSessionInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.session = SessionFactory(owner=self.owner)

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await DeleteSessionInteractor(None, "github").execute(12)

    async def test_delete_session(self):
        await DeleteSessionInteractor(self.owner, "github").execute(
            self.session.sessionid
        )
        with pytest.raises(Session.DoesNotExist):
            await get_session(self.session.sessionid)
