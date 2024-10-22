import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View
from requests.auth import HTTPBasicAuth
from shared.django_apps.codecov_auth.models import Account, OktaSettings, Owner

from codecov_auth.views.okta_mixin import (
    OktaLoginMixin,
    OktaTokenResponse,
    validate_id_token,
)

# The key for accessing the Okta signed in accounts list in the session
OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY = "okta_signed_in_accounts"

# The key for the currently signing in session in Okta.
# This is so that the callback can reference the orgs/accounts that we're
# signing in for.
OKTA_CURRENT_SESSION = "okta_current_session"

log = logging.getLogger(__name__)


def get_app_redirect_url(org_username: str, service: str) -> str:
    """The Codecov app page we redirect users to."""
    return f"{settings.CODECOV_DASHBOARD_URL}/{service}/{org_username}"


def get_oauth_redirect_url() -> str:
    """The Okta callback URL for us to finish the authentication."""
    return f"{settings.CODECOV_API_URL}/login/okta/callback"


def get_okta_settings(organization: Owner) -> OktaSettings | None:
    account: Account | None = organization.account
    if account:
        okta_settings: OktaSettings | None = account.okta_settings.first()
        if okta_settings:
            return okta_settings
    return None


class OktaCloudLoginView(OktaLoginMixin, View):
    service = "okta_cloud"

    def get(
        self, request: HttpRequest, service: str, org_username: str
    ) -> HttpResponse:
        log_context: dict = {"service": service, "username": org_username}
        if not request.user or request.user.is_anonymous:
            log.warning(
                "User needs to be signed in before authenticating organization with Okta.",
                extra=log_context,
            )
            return HttpResponse(status=403)

        try:
            organization: Owner = Owner.objects.get(
                service=service, username=org_username
            )
        except Owner.DoesNotExist:
            log.warning("The organization doesn't exist.", extra=log_context)
            return HttpResponse(status=404)

        okta_settings = get_okta_settings(organization)
        if not okta_settings:
            log.warning(
                "Okta settings not found. Cannot sign into Okta", extra=log_context
            )
            return HttpResponse(status=404)

        app_redirect_url = get_app_redirect_url(
            organization.username, organization.service
        )
        oauth_redirect_url = get_oauth_redirect_url()

        # User is already logged in, redirect them to the org page
        if organization.account.id in request.session.get(
            OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY, []
        ):
            return redirect(app_redirect_url)

        # Otherwise start the process redirect them to the Issuer page to authenticate
        else:
            consent = self._redirect_to_consent(
                iss=okta_settings.url.strip("/ "),
                client_id=okta_settings.client_id,
                oauth_redirect_url=oauth_redirect_url,
            )
            request.session[OKTA_CURRENT_SESSION] = {
                "org_ownerid": organization.ownerid,
                "okta_settings_id": okta_settings.id,
            }
            return consent


class OktaCloudCallbackView(OktaLoginMixin, View):
    service = "okta_cloud"

    def get(self, request: HttpRequest) -> HttpResponse:
        current_okta_session: dict[str, int] | None = request.session.get(
            OKTA_CURRENT_SESSION
        )
        if not current_okta_session:
            log.warning("Trying to sign into Okta with no existing sign-in session.")
            return HttpResponse(status=403)

        org_owner = Owner.objects.get(ownerid=current_okta_session["org_ownerid"])
        log_context: dict = {
            "service": org_owner.service,
            "username": org_owner.username,
        }

        if not request.user or request.user.is_anonymous:
            log.warning(
                "User not logged in for Okta callback.",
                extra=log_context,
            )
            return HttpResponse(status=403)

        try:
            okta_settings = OktaSettings.objects.get(
                id=current_okta_session["okta_settings_id"]
            )
        except OktaSettings.DoesNotExist:
            log.warning(
                "Okta settings not found. Cannot sign into Okta", extra=log_context
            )
            return HttpResponse(status=404)

        app_redirect_url = get_app_redirect_url(org_owner.username, org_owner.service)
        oauth_redirect_url = get_oauth_redirect_url()

        # Check for error in the callback
        error = request.GET.get("error")
        if error:
            log.warning(
                f"Okta authentication error: {error}",
                extra=log_context,
            )
            return redirect(f"{app_redirect_url}?error={error}")

        # Redirect URL, need to validate and mark user as logged in
        if request.GET.get("code"):
            return self._perform_login(
                request,
                org_owner,
                okta_settings,
                app_redirect_url,
                oauth_redirect_url,
            )
        else:
            log.warning(
                "No code is passed. Invalid callback. Cannot sign into Okta",
                extra=log_context,
            )

        return HttpResponse(status=400)

    def _perform_login(
        self,
        request: HttpRequest,
        organization: Owner,
        okta_settings: OktaSettings,
        app_redirect_url: str,
        oauth_redirect_url: str,
    ) -> HttpResponse:
        code = request.GET.get("code")
        state = request.GET.get("state")

        if not self.verify_state(state):
            log.warning("Invalid state during Okta login")
            return redirect(f"{app_redirect_url}?error=invalid_state")

        issuer: str = okta_settings.url.strip("/ ")
        user_data: OktaTokenResponse | None = self._fetch_user_data(
            issuer,
            code,
            state,
            oauth_redirect_url,
            HTTPBasicAuth(okta_settings.client_id, okta_settings.client_secret),
        )

        if user_data is None:
            log.warning("Can't log in. Invalid Okta Token Response", exc_info=True)
            return redirect(f"{app_redirect_url}?error=invalid_token_response")

        try:
            _ = validate_id_token(issuer, user_data.id_token, okta_settings.client_id)
        except Exception as e:
            log.warning(f"Invalid ID token: {str(e)}", exc_info=True)
            return redirect(f"{app_redirect_url}?error=invalid_id_token")

        self._login_user(request, organization)

        return redirect(app_redirect_url)

    def _login_user(self, request: HttpRequest, organization: Owner) -> None:
        """Logging in the user will just mean adding the account to the user's
        okta_logged_in_accounts session.
        """
        okta_signed_in_accounts: list[int] = request.session.get(
            OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY, []
        )
        okta_signed_in_accounts.append(organization.account.id)
        request.session[OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY] = okta_signed_in_accounts
        return
