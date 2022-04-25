import base64
import logging
import re
from urllib.parse import parse_qsl, urlencode, urljoin

import oauth2 as oauth
from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from shared.torngit import BitbucketServer
from shared.torngit.bitbucket_server import signature
from shared.torngit.exceptions import TorngitServerFailureError

from codecov_auth.models import SERVICE_BITBUCKET_SERVER
from codecov_auth.views.base import LoginMixin

log = logging.getLogger(__name__)

# TODO: Implement this handler
# The legacy one was broken.
# There are no clients for this right now, so we're skipping it. (2022-04-07)
class BitbucketServerLoginView(View, LoginMixin):
    service = SERVICE_BITBUCKET_SERVER
    # Legacy links that I copied.
    # Probably should go in shared (get_authenticated_user)
    # https://github.com/codecov/codecov.io/blob/54568e8deab82c3c77e5d313a182cfe9a93f3154/app/handlers/bitbucket_server/login.py#L35
    # _OAUTH_WHOAMI = settings.BITBUCKET_SERVER_URL + "/plugins/servlet/applinks/whoami"
    # _OAUTH_VERSION = "1.0"

    @async_to_sync
    async def fetch_user_data(self, token):
        repo_service = BitbucketServer(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_SERVER_CLIENT_ID,
                secret=settings.BITBUCKET_SERVER_CLIENT_SECRET,
            ),
            token=token,
        )
        user_data = await repo_service.get_authenticated_user()
        authenticated_user = {
            "access_token": token,
            "id": user_data["uuid"][1:-1],
            "login": user_data.pop("username"),
        }
        user_orgs = await repo_service.list_teams()
        return dict(
            user=authenticated_user,
            orgs=user_orgs,
            is_student=False,
            has_private_access=True,
        )

    @async_to_sync
    async def redirect_to_bitbucket_server_step(self, request):
        # For this part we need a client with no token
        # And the consumer needs to have the defined client id. The secret is ignored.
        # https://developer.atlassian.com/server/jira/platform/oauth/
        consumer = oauth.Consumer(settings.BITBUCKET_SERVER_CLIENT_ID, "")
        client = oauth.Client(consumer)
        client.set_signature_method(signature)

        if request.GET.get("redirect"):
            self.set_cookie(
                "login-redirect",
                request.GET.get["redirect"],
                httponly=True,
                expires_days=1,
            )
        # In this part we make a request for the unauthorized request token.
        # Here the user will be redirected to the authorize page and allow our app to be used.
        # At the end of this step client will see a screen saying "you have authorized this application. Return to application and click continue."
        request_token_url = (
            f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/request-token"
        )
        resp, content = client.request(request_token_url, "POST")
        if resp["status"] != "200":
            raise Exception("Invalid response %s: %s" % (resp["status"], content))
        request_token = {
            k.decode("utf-8"): v for k, v in dict(parse_qsl(content)).items()
        }
        auth_token = request_token["oauth_token"]
        auth_token_secret = request_token["oauth_token_secret"]

        data = (
            base64.b64encode(auth_token) + b"|" + base64.b64encode(auth_token_secret)
        ).decode()

        url_params = urlencode(dict(oauth_token=auth_token))
        authorize_url = f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/authorize?{url_params}"
        response = redirect(authorize_url)
        response.set_cookie(
            "_oauth_request_token", data, domain=settings.COOKIES_DOMAIN
        )
        self.store_to_cookie_utm_tags(response)
        return response

    def actual_login_step(self, request):
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
        consumer = oauth.Consumer(settings.BITBUCKET_SERVER_CLIENT_ID, "")
        token = oauth.Token(cookie_key, cookie_secret)
        client = oauth.Client(consumer, token)
        client.set_signature_method(signature)

        # Get the access token from the request token
        # The access token can be stored and reused.
        response = redirect(settings.CODECOV_DASHBOARD_URL + "/bbs")
        response.delete_cookie("_oauth_request_token", domain=settings.COOKIES_DOMAIN)
        access_token_url = (
            f"{settings.BITBUCKET_SERVER_URL}/plugins/servlet/oauth/access-token"
        )
        resp, content = client.request(access_token_url, "POST")
        if resp["status"] != "200":
            raise Exception("Invalid response %s: %s" % (resp["status"], content))
        access_token = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in dict(parse_qsl(content)).items()
        }
        auth_token = access_token["oauth_token"]
        auth_token_secret = access_token["oauth_token_secret"]

        user_dict = self.fetch_user_data(oauth.Token(auth_token, auth_token_secret))
        user = self.login_from_user_dict(user_dict, request, response)
        log.info("User successfully logged in", extra=dict(ownerid=user.ownerid))
        return response

    def get(self, request):
        try:
            if request.COOKIES.get("_oauth_request_token"):
                log.info("Logging into bitbucket_server after authorization")
                return self.actual_login_step(request)
            else:
                log.info("Redirecting user to bitbucket_server for authorization")
                return self.redirect_to_bitbucket_server_step(request)
        except TorngitServerFailureError:
            log.warning("Bitbucket Server not available for login")
            return redirect(reverse("bbs-login"))
