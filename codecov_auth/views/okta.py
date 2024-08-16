import logging

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View
from requests.auth import HTTPBasicAuth

from codecov_auth.models import OktaUser, User
from codecov_auth.views.base import LoginMixin
from codecov_auth.views.okta_mixin import (
    ISS_REGEX,
    OktaLoginMixin,
    OktaTokenResponse,
    validate_id_token,
)
from utils.services import get_short_service_name

log = logging.getLogger(__name__)

OKTA_BASIC_AUTH = HTTPBasicAuth(
    settings.OKTA_OAUTH_CLIENT_ID, settings.OKTA_OAUTH_CLIENT_SECRET
)


class OktaLoginView(LoginMixin, OktaLoginMixin, View):
    service = "okta"

    def _perform_login(self, request: HttpRequest, iss: str) -> HttpResponse:
        code = request.GET.get("code")
        state = request.GET.get("state")

        if not self.verify_state(state):
            log.warning("Invalid state during Okta login")
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        user_data: OktaTokenResponse | None = self._fetch_user_data(
            iss, code, state, settings.OKTA_OAUTH_REDIRECT_URL, OKTA_BASIC_AUTH
        )
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

        return response

    def _login_user(
        self, request: HttpRequest, iss: str, user_data: OktaTokenResponse
    ) -> User:
        id_token = user_data.id_token
        id_payload = validate_id_token(iss, id_token, settings.OKTA_OAUTH_CLIENT_ID)

        okta_id = id_payload.sub
        user_email = id_payload.email
        user_name = id_payload.name

        okta_user = OktaUser.objects.filter(okta_id=okta_id).first()

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
                access_token=user_data.access_token,
            )
            log.info(
                "Created Okta user",
                extra=dict(okta_user_id=okta_user.pk),
            )

        login(request, current_user)
        return current_user

    def validate_issuer(self) -> str | None:
        """Checks that the issuer is valid. If not, it returns None."""
        iss = settings.OKTA_ISS
        if iss is None:
            log.warning("Unable to log in due to missing Okta issuer", exc_info=True)
            return None
        if not ISS_REGEX.match(iss):
            log.warning("Invalid Okta issuer")
            return None
        return iss

    def get(self, request: HttpRequest) -> HttpResponse:
        iss = self.validate_issuer()
        if iss is None:
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        if request.GET.get("code"):
            return self._perform_login(request, iss)
        else:
            response = self._redirect_to_consent(
                iss=iss,
                client_id=settings.OKTA_OAUTH_CLIENT_ID,
                oauth_redirect_url=settings.OKTA_OAUTH_REDIRECT_URL,
            )
            self.store_to_cookie_utm_tags(response)
            return response
