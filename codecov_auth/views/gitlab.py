import logging
from urllib.parse import urlencode, urljoin
from uuid import uuid4  # noqa: F401

from asgiref.sync import async_to_sync
from django.conf import settings
from django.shortcuts import redirect
from django.views import View
from shared.django_apps.codecov_metrics.service.codecov_metrics import (
    UserOnboardingMetricsService,
)
from shared.torngit import Gitlab
from shared.torngit.exceptions import TorngitError

from codecov_auth.views.base import LoginMixin, StateMixin

log = logging.getLogger(__name__)


class GitlabLoginView(LoginMixin, StateMixin, View):
    service = "gitlab"
    error_redirection_page = "/"

    @property
    def repo_service_instance(self):
        return Gitlab(
            oauth_consumer_token=dict(
                key=settings.GITLAB_CLIENT_ID, secret=settings.GITLAB_CLIENT_SECRET
            )
        )

    @property
    def redirect_info(self):
        return dict(
            redirect_uri=settings.GITLAB_REDIRECT_URI,
            repo_service=Gitlab(),
            client_id=settings.GITLAB_CLIENT_ID,
        )

    def get_url_to_redirect_to(self):
        redirect_info = self.redirect_info
        base_url = urljoin(redirect_info["repo_service"].service_url, "oauth/authorize")
        state = self.generate_state()

        scope = settings.GITLAB_SCOPE
        log.info(f"Gitlab oauth with scope: '{scope}'")

        query = dict(
            response_type="code",
            client_id=redirect_info["client_id"],
            redirect_uri=redirect_info["redirect_uri"],
            state=state,
            scope=scope,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    @async_to_sync
    async def fetch_user_data(self, request, code):
        repo_service = self.repo_service_instance
        user_dict = await repo_service.get_authenticated_user(code)
        user_dict["login"] = user_dict["username"]
        # Comply to torngit's token encoding
        user_dict["key"] = user_dict["access_token"]
        user_orgs = await repo_service.list_teams()
        return dict(
            user=user_dict, orgs=user_orgs, is_student=False, has_private_access=True
        )

    def actual_login_step(self, request):
        state = request.GET.get("state")
        code = request.GET.get("code")
        try:
            user_dict = self.fetch_user_data(request, code)
        except TorngitError:
            log.warning("Unable to log in due to problem on Gitlab", exc_info=True)
            return redirect(self.error_redirection_page)
        user = self.get_and_modify_owner(user_dict, request)
        redirection_url, is_valid = self.get_redirection_url_from_state(state)
        if not is_valid:
            return redirect(redirection_url)
        redirection_url = self.modify_redirection_url_based_on_default_user_org(
            redirection_url, user
        )
        response = redirect(redirection_url)
        self.login_owner(user, request, response)
        self.remove_state(state, delay=5)
        UserOnboardingMetricsService.create_user_onboarding_metric(
            org_id=user.ownerid, event="INSTALLED_APP", payload={"login": "gitlab"}
        )
        return response

    def get(self, request):
        if settings.DISABLE_GIT_BASED_LOGIN and request.user.is_anonymous:
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        if request.GET.get("code"):
            return self.actual_login_step(request)
        else:
            url_to_redirect_to = self.get_url_to_redirect_to()
            response = redirect(url_to_redirect_to)
            self.store_to_cookie_utm_tags(response)
            return response
