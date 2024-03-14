import json
import logging
import re
from typing import Dict, Optional
from urllib.parse import urlencode

import jwt
import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View
from requests.auth import HTTPBasicAuth

from codecov_auth.models import OktaUser, User
from codecov_auth.views.base import LoginMixin, StateMixin
from utils.services import get_short_service_name

log = logging.getLogger(__name__)
iss_regex = re.compile(r"https://[\w\d\-\_]+.okta.com/?")


def validate_id_token(iss: str, id_token: str) -> dict:
    res = requests.get(f"{iss}/oauth2/v1/keys")
    jwks = res.json()

    public_keys = {}
    for jwk in jwks["keys"]:
        kid = jwk["kid"]
        public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    kid = jwt.get_unverified_header(id_token)["kid"]
    key = public_keys[kid]

    id_payload = jwt.decode(
        id_token,
        key=key,
        algorithms=["RS256"],
        audience=settings.OKTA_OAUTH_CLIENT_ID,
    )
    assert id_payload["iss"] == iss
    assert id_payload["aud"] == settings.OKTA_OAUTH_CLIENT_ID

    return id_payload


auth = HTTPBasicAuth(settings.OKTA_OAUTH_CLIENT_ID, settings.OKTA_OAUTH_CLIENT_SECRET)


class OktaLoginView(LoginMixin, StateMixin, View):
    service = "okta"

    def _fetch_user_data(self, iss: str, code: str, state: str) -> Optional[Dict]:
        res = requests.post(
            f"{iss}/oauth2/v1/token",
            auth=auth,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OKTA_OAUTH_REDIRECT_URL,
                "state": state,
            },
        )

        if not self.verify_state(state):
            log.warning("Invalid state during Okta OAuth")
            return None

        if res.status_code >= 400:
            return None
        return res.json()

    def _redirect_to_consent(self, iss: str) -> HttpResponse:
        state = self.generate_state()
        qs = urlencode(
            dict(
                response_type="code",
                client_id=settings.OKTA_OAUTH_CLIENT_ID,
                scope="openid email profile",
                redirect_uri=settings.OKTA_OAUTH_REDIRECT_URL,
                state=state,
            )
        )
        redirect_url = f"{iss}/oauth2/v1/authorize?{qs}"
        response = redirect(redirect_url)
        self.store_to_cookie_utm_tags(response)

        if settings.OKTA_ISS is None:
            # ISS was passed to us from Okta
            self._store_iss_cookie(iss, response)

        return response

    def _store_iss_cookie(self, iss: str, response: HttpResponse):
        response.set_cookie(
            "_okta_iss",
            iss,
            max_age=86400,  # Same as state validatiy
            httponly=True,
            domain=settings.COOKIES_DOMAIN,
        )

    def _perform_login(self, request: HttpRequest) -> HttpResponse:
        code = request.GET.get("code")
        state = request.GET.get("state")

        if not self.verify_state(state):
            log.warning("Invalid state during Okta login")
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        iss = settings.OKTA_ISS or request.COOKIES.get("_okta_iss")
        if iss is None:
            log.warning("Unable to log in due to missing Okta issuer", exc_info=True)
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        user_data = self._fetch_user_data(iss, code, state)
        if user_data is None:
            log.warning("Unable to log in due to problem on Okta", exc_info=True)
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        current_user = self._login_user(request, iss, user_data)

        # TEMPORARY: we're assuming a single owner for the time being since there's
        # no supporting UI to select which owner you'd like to view
        owner = current_user.owners.first()
        self.remove_state(state)
        if owner is not None:
            service = get_short_service_name(owner.service)
            response = redirect(f"{settings.CODECOV_DASHBOARD_URL}/{service}")
        else:
            # user has not connected any owners yet
            response = redirect(f"{settings.CODECOV_DASHBOARD_URL}/sync")

        response.delete_cookie("_okta_iss")
        return response

    def _login_user(self, request: HttpRequest, iss: str, user_data: dict):
        id_token = user_data[
            "id_token"
        ]  # this will be present since we requested the `oidc` scope
        id_payload = validate_id_token(iss, id_token)

        okta_id = id_payload["sub"]
        user_email = id_payload["email"]
        user_name = id_payload["name"]

        okta_user = OktaUser.objects.filter(okta_id=okta_id).first()

        current_user = None
        if request.user is not None and not request.user.is_anonymous:
            # we're already authenticated
            current_user = request.user

            if okta_user and okta_user.user != request.user:
                log.warning(
                    "Okta account already linked to another user",
                    extra=dict(
                        current_user_id=request.user.pk, okta_user_id=okta_user.pk
                    ),
                )
                # Logout the current user and login the user who already
                # claimed this Okta account (below)
                logout(request)
                current_user = okta_user.user
        else:
            # we're not authenticated
            if okta_user:
                log.info(
                    "Existing Okta user logging in",
                    extra=dict(okta_user_id=okta_user.pk),
                )
                current_user = okta_user.user
            else:
                current_user = User.objects.create(
                    name=user_name,
                    email=user_email,
                )

        if okta_user is None:
            okta_user = OktaUser.objects.create(
                user=current_user,
                okta_id=okta_id,
                name=user_name,
                email=user_email,
                access_token=user_data["access_token"],
            )
            log.info(
                "Created Okta user",
                extra=dict(okta_user_id=okta_user.pk),
            )

        login(request, current_user)
        return current_user

    def get(self, request):
        if request.GET.get("code"):
            return self._perform_login(request)
        else:
            iss = settings.OKTA_ISS or request.GET.get("iss")
            if not iss:
                log.warning("Missing Okta issuer")
                return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")
            if not iss_regex.match(iss):
                log.warning("Invalid Okta issuer")
                return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")
            return self._redirect_to_consent(iss=iss)
