from django.test import TestCase
from django.test.client import Client


class ViewTest(TestCase):
    def test_redirect_app(self):
        client = Client()
        response = client.get(
            "/redirect_app/gh/codecov/codecov.io/settings", follow=False
        )
        self.assertRedirects(
            response,
            "http://localhost:3000/gh/codecov/codecov.io/settings",
            302,
            fetch_redirect_response=False,
        )

    def test_health(self):
        client = Client()
        response = client.get("")
        assert response.status_code == 200
