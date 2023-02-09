import base64
import logging
import re
import threading
from urllib.parse import parse_qsl, urlencode, urljoin

import oauth2 as oauth
from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from shared.torngit import BitbucketServer
from shared.torngit.exceptions import (
    TorngitClientGeneralError,
    TorngitServerFailureError,
)

from codecov_auth.models import SERVICE_BITBUCKET_SERVER
from codecov_auth.views.base import LoginMixin

log = logging.getLogger(__name__)


class BitbucketServerLoginView(View, LoginMixin):
    service = SERVICE_BITBUCKET_SERVER

    async def fetch_user_data(self, token):
        repo_service = BitbucketServer(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_SERVER_CLIENT_ID,
                secret=settings.BITBUCKET_SERVER_CLIENT_SECRET,
            ),
            token=oauth.Token(token["key"], token["secret"]),
        )
        # Whoami? Get the user
        # https://answers.atlassian.com/questions/9379031/answers/9379803
        whoami_url = f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/applinks/whoami"
        username = await repo_service.api("GET", whoami_url)
        # https://developer.atlassian.com/static/rest/bitbucket-server/4.0.1/bitbucket-rest.html#idp2649152
        user = await repo_service.api("GET", "/users/%s" % username)

        authenticated_user = {
            "key": token["key"],
            "secret": token["secret"],
            "id": user["id"],
            "login": user["name"],
        }
        user_orgs = await repo_service.list_teams()
        return dict(
            user=authenticated_user,
            orgs=user_orgs,
            is_student=False,
            has_private_access=True,
        )

    async def redirect_to_bitbucket_server_step(self, request):
        # And the consumer needs to have the defined client id. The secret is ignored.
        # https://developer.atlassian.com/server/jira/platform/oauth/
        repo_service = BitbucketServer(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_SERVER_CLIENT_ID,
                secret="",
            )
        )
        # In this part we make a request for the unauthorized request token.
        # Here the user will be redirected to the authorize page and allow our app to be used.
        # At the end of this step client will see a screen saying "you have authorized this application. Return to application and click continue."
        request_token_url = (
            f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/request-token"
        )
        request_token = await repo_service.api("POST", request_token_url)

        auth_token = request_token["oauth_token"]
        auth_token_secret = request_token["oauth_token_secret"]

        data = (
            base64.b64encode(auth_token.encode())
            + b"|"
            + base64.b64encode(auth_token_secret.encode())
        ).decode()

        url_params = urlencode(dict(oauth_token=auth_token))
        authorize_url = f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/authorize?{url_params}"
        response = redirect(authorize_url)
        response.set_cookie(
            "_oauth_request_token", data, domain=settings.COOKIES_DOMAIN
        )
        self.store_to_cookie_utm_tags(response)
        return response

    async def actual_login_step(self, request):
        # Retrieve the authorized request_token and create a new client
        # This new client has the same consumer as before, but uses the request token.
        # ! Each request_token can only be used once
        request_cookie = request.COOKIES.get("_oauth_request_token")
        if not request_cookie:
            log.warning(
                "Request arrived with proper url params but not the proper cookies"
            )
            return redirect(reverse("bbs-login"))

        cookie_key, cookie_secret = [
            base64.b64decode(i).decode() for i in request_cookie.split("|")
        ]
        token = oauth.Token(cookie_key, cookie_secret)
        repo_service = BitbucketServer(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_SERVER_CLIENT_ID,
                secret=settings.BITBUCKET_SERVER_CLIENT_SECRET,
            ),
            token=token,
        )
        # Get the access token from the request token
        # The access token can be stored and reused.
        response = redirect(settings.CODECOV_DASHBOARD_URL + "/bbs")
        response.delete_cookie("_oauth_request_token", domain=settings.COOKIES_DOMAIN)
        access_token_url = (
            f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/access-token"
        )
        access_token = await repo_service.api("POST", access_token_url)
        auth_token = access_token["oauth_token"]
        auth_token_secret = access_token["oauth_token_secret"]

        user_dict = await self.fetch_user_data(
            dict(key=auth_token, secret=auth_token_secret)
        )

        def async_login():
            user = self.login_from_user_dict(user_dict, request, response)
            log.info(
                "User (async) successfully logged in", extra=dict(ownerid=user.ownerid)
            )

        force_sync = threading.Thread(target=async_login)
        force_sync.start()
        force_sync.join()
        return response

    @async_to_sync
    async def get(self, request):
        try:
            if request.COOKIES.get("_oauth_request_token"):
                log.info("Logging into bitbucket_server after authorization")
                return await self.actual_login_step(request)
            else:
                log.info("Redirecting user to bitbucket_server for authorization")
                return await self.redirect_to_bitbucket_server_step(request)
        except TorngitServerFailureError:
            log.warning("Bitbucket Server not available for login")
            return redirect(settings.CODECOV_DASHBOARD_URL + "/bbs")
