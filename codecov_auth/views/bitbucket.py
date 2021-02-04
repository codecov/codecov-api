import asyncio
import base64
import logging

from django.shortcuts import redirect
from django.urls import reverse
from shared.torngit import Bitbucket
from urllib.parse import urlencode
from django.views import View
from django.conf import settings
from codecov_auth.views.base import LoginMixin

log = logging.getLogger(__name__)


class BitbucketLoginView(View, LoginMixin):
    cookie_prefix = "bitbucket"

    def get_is_enterprise(self):
        # TODO Change when rolling out enterprise
        return False

    async def fetch_user_data(self, token):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            ),
            token=token,
        )
        stuff_to_save = "%(key)s:%(secret)s" % token
        user_data = await repo_service.get_authenticated_user()
        authenticated_user = {
            "access_token": stuff_to_save,
            "id": user_data.pop("account_id"),
            "login": user_data.pop("username"),
        }
        user_orgs = await repo_service.list_teams()
        return dict(
            user=authenticated_user,
            orgs=user_orgs,
            is_student=False,
            has_private_access=False,
        )

    def redirect_to_bitbucket_step(self, request):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            ),
        )
        oauth_token_pair = repo_service.generate_request_token(
            settings.BITBUCKET_REDIRECT_URI
        )
        oauth_token = oauth_token_pair["oauth_token"]
        oauth_token_secret = oauth_token_pair["oauth_token_secret"]
        url_params = urlencode({"oauth_token": oauth_token})
        url_to_redirect = f"{Bitbucket._OAUTH_AUTHORIZE_URL}?{url_params}"
        response = redirect(url_to_redirect)
        data = (
            base64.b64encode(oauth_token.encode())
            + b"|"
            + base64.b64encode(oauth_token_secret.encode())
        ).decode()
        response.set_cookie("_oauth_request_token", data)
        return response

    def actual_login_step(self, request):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            ),
        )
        oauth_verifier = request.GET.get("oauth_verifier")
        # we use an unsigned cookie here because that's what tornado also does
        # and we are keeping compaitiblity with them for a bit
        request_cookie = request.COOKIES.get("_oauth_request_token")
        if not request_cookie:
            log.warning(
                "Request arrived with proper url params but not the proper cookies"
            )
            return redirect(reverse("bitbucket-login"))
        cookie_key, cookie_secret = [
            base64.b64decode(i).decode() for i in request_cookie.split("|")
        ]
        token = repo_service.generate_access_token(
            cookie_key, cookie_secret, oauth_verifier
        )
        user_dict = asyncio.run(self.fetch_user_data(token))
        response = redirect("/bb")
        response.delete_cookie("_oauth_request_token")
        self.login_from_user_dict(user_dict, request, response)
        return response

    def get(self, request):
        if request.GET.get("oauth_verifier"):
            log.info("Logging into Bitbucket")
            return self.actual_login_step(request)
        else:
            return self.redirect_to_bitbucket_step(request)
