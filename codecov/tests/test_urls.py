from django.test import TestCase
from django.test.client import Client


class ViewTest(TestCase):
    def test_health(self):
        client = Client()
        response = client.get("")
        assert response.status_code == 200
