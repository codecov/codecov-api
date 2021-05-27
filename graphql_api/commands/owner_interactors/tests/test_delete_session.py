from asgiref.sync import sync_to_async
import pytest
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser

from codecov_auth.models import Session
from codecov_auth.tests.factories import OwnerFactory, SessionFactory

from graphql_api.commands.owner_interactors.delete_session import (
    DeleteSessionInteractor,
)
from graphql_api.commands.exceptions import Unauthenticated


@sync_to_async
def get_session(id):
    return Session.objects.get(sessionid=id)


class DeleteSessionInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.session = SessionFactory(owner=self.user)

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await DeleteSessionInteractor(AnonymousUser()).execute(12)

    async def test_delete_session(self):
        await DeleteSessionInteractor(self.user).execute(self.session.sessionid)
        with pytest.raises(Session.DoesNotExist):
            await get_session(self.session.sessionid)
