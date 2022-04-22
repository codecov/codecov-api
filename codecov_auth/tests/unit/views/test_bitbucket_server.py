from unittest.mock import patch

import pytest
from django.http.cookie import SimpleCookie
from django.test import TestCase, override_settings
from django.urls import reverse
from shared.torngit.bitbucket_server import BitbucketServer
from shared.torngit.exceptions import TorngitServer5xxCodeError

from codecov_auth.models import Owner
from codecov_auth.views.bitbucket_server import BitbucketServerLoginView
from utils.encryption import encryptor


@override_settings(BITBUCKET_SERVER_CLIENT_ID="this-is-the-important-bit")
@override_settings(BITBUCKET_SERVER_URL="https://bitbucket.codecov.dev")
def test_get_bbs_redirect(client, settings, mocker):
    client_request_mock = mocker.patch(
        "codecov_auth.views.bitbucket_server.oauth.Client.request",
        side_effect=lambda *args: (dict(status='200'), b'oauth_token=SomeToken&oauth_token_secret=SomeTokenSecret' ),
    )
    url = reverse("bbs-login")
    res = client.get(url, SERVER_NAME="localhost:8000")

    assert res.status_code == 302
    assert res.url == 'https://bitbucket.codecov.dev/plugins/servlet/oauth/authorize?oauth_token=SomeToken'
    client_request_mock.assert_called_with('https://bitbucket.codecov.dev/plugins/servlet/oauth/request-token', 'POST')
