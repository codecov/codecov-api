from django.test import TestCase, override_settings
from django.urls import reverse

from codecov_auth.tests.factories import OwnerFactory
from utils.test_utils import Client


@override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:3000"])
class MiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_whitelisted_origin(self):
        res = self.client.get("/health", headers={"Origin": "http://localhost:3000"})

        assert res.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert res.headers["Access-Control-Allow-Credentials"] == "true"

    def test_non_whitelisted_origin(self):
        res = self.client.get("/health", headers={"Origin": "http://example.com"})

        assert res.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert "Access-Control-Allow-Credentials" not in res.headers


@override_settings(GUEST_ACCESS=False)
@override_settings(IS_ENTERPRISE=True)
class GuestAccessMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_guest_access_disabled(self):
        res = self.client.get("/health/")

        assert res.status_code == 401
        assert res.json() == {"error": "Unauthorized guest access"}

    def test_guest_access_user_authenticated(self):
        owner = OwnerFactory()
        self.client.force_login_owner(owner)
        kwargs = {"service": owner.service, "owner_username": owner.username}
        res = self.client.get("/health/", kwargs=kwargs)

        assert res.status_code == 200
        assert res.headers["Content-Type"] == "text/html; charset=utf-8"

    def test_guest_user_login(self):
        res = self.client.get(reverse("gh-login"))

        assert res.status_code == 302
        assert res.headers["Content-Type"] == "text/html; charset=utf-8"
