import json
from unittest.mock import patch

from django.urls import reverse

from codecov_auth.models import Owner
from codecov_auth.views.bitbucket_server import BitbucketServerLoginView
from utils.encryption import encryptor


def test_get_bbs_redirect(client, settings, mocker):
    client_request_mock = mocker.patch(
        "codecov_auth.views.bitbucket_server.oauth.Client.request",
        side_effect=lambda *args, **kwargs: (
            { "content-type":"application/json", "status":"200" },
            json.dumps({ "oauth_token": "SomeToken", "oauth_token_secret": "SomeTokenSecret" } ),
        ),
    )
    settings.BITBUCKET_SERVER_CLIENT_ID = "this-is-the-important-bit"
    settings.BITBUCKET_SERVER_URL = "https://my.bitbucketserver.com"
    url = reverse("bbs-login")
    res = client.get(url, SERVER_NAME="localhost:8000")

    assert res.status_code == 302
    assert (
        res.url
        == "https://my.bitbucketserver.com/plugins/servlet/oauth/authorize?oauth_token=SomeToken"
    )
    client_request_mock.assert_called()
