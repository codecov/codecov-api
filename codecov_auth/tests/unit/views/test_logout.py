from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from utils.test_utils import Client


class LogoutViewTest(TransactionTestCase):
    def _get(self, url):
        return self.client.get(url, content_type="application/json")

    def _is_authenticated(self):
        response = self.client.post(
            "/graphql/gh",
            {"query": "{ me { user { username } } }"},
            content_type="application/json",
        )
        return response.json()["data"]["me"] is not None

    def test_logout_when_unauthenticated(self):
        res = self._get("/logout/gh")
        assert res.status_code == 302

    def test_logout_when_authenticated(self):
        owner = OwnerFactory()
        self.client = Client()
        self.client.force_login_owner(owner)

        res = self._get("/graphql/gh/")
        self.assertEqual(self._is_authenticated(), True)

        res = self._get("/logout/gh")
        assert res.url == "/"
        self.assertEqual(res.status_code, 302)

        res = self._get("/graphql/gh/")
        self.assertEqual(self._is_authenticated(), False)
