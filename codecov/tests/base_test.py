import json

from django.conf import settings
from django.test import TestCase


class InternalAPITest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # internal apis are behind a debug flag currently
        # and django/pytest set DEBUG to false by default
        # https://docs.djangoproject.com/en/dev/topics/testing/overview/#other-test-conditions
        settings.DEBUG = True

    @staticmethod
    def json_content(response):
        return json.loads(response.content.decode())