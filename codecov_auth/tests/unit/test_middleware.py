from django.test import TestCase, override_settings

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
        res = self.client.get("/health")

        assert res.status_code == 401
        assert res.json() == {"error": "Unauthorized guest access"}
