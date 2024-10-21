from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from utils.test_utils import Client


class LogoutViewTest(TransactionTestCase):
    def _get(self, url):
        return self.client.get(url, content_type="application/json")

    def _post(self, url):
        return self.client.post(url, content_type="application/json")

    def _is_authenticated(self):
        response = self.client.post(
            "/graphql/gh",
            {"query": "{ me { user { username } } }"},
            content_type="application/json",
        )
        return response.json()["data"]["me"] is not None

    def test_logout_when_unauthenticated(self):
        res = self._post("/logout")
        assert res.status_code == 401

    def test_logout_when_authenticated(self):
        owner = OwnerFactory()
        self.client = Client()
        self.client.force_login_owner(owner)

        res = self._post("/graphql/gh/")
        self.assertEqual(self._is_authenticated(), True)

        res = self._post("/logout")
        self.assertEqual(res.status_code, 205)

        res = self._get("/graphql/gh/")
        self.assertEqual(self._is_authenticated(), False)
