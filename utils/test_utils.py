from django.test.client import Client as DjangoClient
from rest_framework.test import APIClient as DjangoAPIClient

from codecov_auth.models import Owner


class BaseTestCase(object):
    pass


class ClientMixin:
    def force_login_owner(self, owner: Owner):
        self.force_login(user=owner.user)
        session = self.session
        session["current_owner_id"] = owner.pk
        session.save()

    def logout(self):
        session = self.session
        session["current_owner_id"] = None
        session.save()
        super().logout()


class Client(ClientMixin, DjangoClient):
    pass


class APIClient(ClientMixin, DjangoAPIClient):
    pass
