import base64
import logging
from urllib.parse import urlencode

from asgiref.sync import async_to_sync
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from shared.django_apps.codecov_metrics.service.codecov_metrics import (
    UserOnboardingMetricsService,
)
from shared.torngit import Bitbucket
from shared.torngit.exceptions import TorngitServerFailureError

from codecov_auth.views.base import LoginMixin
from utils.encryption import encryptor

log = logging.getLogger(__name__)


class BitbucketLoginView(View, LoginMixin):
    service = "bitbucket"

    @async_to_sync
    async def fetch_user_data(self, token):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            ),
            token=token,
        )
        user_data = await repo_service.get_authenticated_user()
        authenticated_user = {
            "key": token["key"],
            "secret": token["secret"],
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

    def redirect_to_bitbucket_step(self, request):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            )
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
        response.set_signed_cookie(
            "_oauth_request_token",
            encryptor.encode(data).decode(),
            domain=settings.COOKIES_DOMAIN,
        )
        self.store_to_cookie_utm_tags(response)
        return response

    def actual_login_step(self, request):
        repo_service = Bitbucket(
            oauth_consumer_token=dict(
                key=settings.BITBUCKET_CLIENT_ID,
                secret=settings.BITBUCKET_CLIENT_SECRET,
            )
        )
        oauth_verifier = request.GET.get("oauth_verifier")
        request_cookie = request.get_signed_cookie("_oauth_request_token", default=None)
        if not request_cookie:
            log.warning(
                "Request arrived with proper url params but not the proper cookies"
            )
            return redirect(reverse("bitbucket-login"))
        request_cookie = encryptor.decode(request_cookie)
        cookie_key, cookie_secret = [
            base64.b64decode(i).decode() for i in request_cookie.split("|")
        ]
        token = repo_service.generate_access_token(
            cookie_key, cookie_secret, oauth_verifier
        )
        user_dict = self.fetch_user_data(token)
        user = self.get_and_modify_owner(user_dict, request)
        redirection_url = settings.CODECOV_DASHBOARD_URL + "/bb"
        redirection_url = self.modify_redirection_url_based_on_default_user_org(
            redirection_url, user
        )
        response = redirect(redirection_url)
        response.delete_cookie("_oauth_request_token", domain=settings.COOKIES_DOMAIN)
        self.login_owner(user, request, response)
        log.info("User successfully logged in", extra=dict(ownerid=user.ownerid))
        UserOnboardingMetricsService.create_user_onboarding_metric(
            org_id=user.ownerid, event="INSTALLED_APP", payload={"login": "bitbucket"}
        )
        return response

    def get(self, request):
        if settings.DISABLE_GIT_BASED_LOGIN and request.user.is_anonymous:
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        try:
            if request.GET.get("oauth_verifier"):
                log.info("Logging into bitbucket after authorization")
                return self.actual_login_step(request)
            else:
                log.info("Redirecting user to bitbucket for authorization")
                return self.redirect_to_bitbucket_step(request)
        except TorngitServerFailureError:
            log.warning("Bitbucket not available for login")
            return redirect(reverse("bitbucket-login"))
