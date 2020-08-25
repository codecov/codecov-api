import json

from django.conf import settings
from django.test.client import Client
from django.test import TestCase

import pytest

class ViewTest(TestCase):
    def test_redirect_app(self, env_setting, expected_url):
        client = Client()
        response = client.get('/redirect_app/gh/codecov/codecov.io/settings', follow=False)
        self.assertRedirects(response,expected_url, 302, fetch_redirect_response=False)

