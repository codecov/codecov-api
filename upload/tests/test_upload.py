from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status
from unittest.mock import patch
from json import dumps
from yaml import YAMLError

from django.conf import settings
from django.test import RequestFactory


class TestUploadHandler(APITestCase):

    # Wrap client calls
    def _options(self, kwargs=None, data=None):
        return self.client.options(reverse("upload-handler", kwargs=kwargs))

    def _post(self, kwargs=None, data=None):
        return self.client.post(reverse("upload-handler", kwargs=kwargs), data=data)

    # Test headers
    def test_options_headers(self):
        response = self._options(kwargs={"version": "v2"})

        headers = response._headers

        assert headers["accept"] == ("Accept", "text/*")
        assert headers["access-control-allow-origin"] == (
            "Access-Control-Allow-Origin",
            "*",
        )
        assert headers["access-control-allow-method"] == (
            "Access-Control-Allow-Method",
            "POST",
        )
        assert headers["access-control-allow-headers"] == (
            "Access-Control-Allow-Headers",
            "Origin, Content-Type, Accept, X-User-Agent",
        )

    def test_post_headers(self):
        with self.subTest("v2"):
            response = self._post(kwargs={"version": "v2"})

            headers = response._headers

            assert headers["access-control-allow-origin"] == (
                "Access-Control-Allow-Origin",
                "*",
            )
            assert headers["access-control-allow-headers"] == (
                "Access-Control-Allow-Headers",
                "Origin, Content-Type, Accept, X-User-Agent",
            )
            assert headers["content-type"] != ("Content-Type", "text/plain",)

        with self.subTest("v4"):
            response = self._post(kwargs={"version": "v4"})

            headers = response._headers

            assert headers["access-control-allow-origin"] == (
                "Access-Control-Allow-Origin",
                "*",
            )
            assert headers["access-control-allow-headers"] == (
                "Access-Control-Allow-Headers",
                "Origin, Content-Type, Accept, X-User-Agent",
            )
            assert headers["content-type"] == ("Content-Type", "text/plain",)
