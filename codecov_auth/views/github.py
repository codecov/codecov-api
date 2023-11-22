import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, urljoin

from asgiref.sync import async_to_sync
from django.conf import settings
from django.shortcuts import redirect
from django.views import View
from shared.torngit import Github
from shared.torngit.exceptions import TorngitError

from codecov_auth.views.base import LoginMixin, StateMixin
from utils.config import get_config

log = logging.getLogger(__name__)


class GithubLoginView(LoginMixin, StateMixin, View):
    service = "github"
    error_redirection_page = "/"

    @property
    def repo_service_instance(self):
        return Github(
            oauth_consumer_token=dict(
                key=settings.GITHUB_CLIENT_ID, secret=settings.GITHUB_CLIENT_SECRET
            )
        )

    @property
    def redirect_info(self):
        return dict(repo_service=Github(), client_id=settings.GITHUB_CLIENT_ID)

    def get_url_to_redirect_to(self, scope):
        redirect_info = self.redirect_info
        redirect_host = (
            redirect_info["repo_service"].service_url
            if redirect_info["repo_service"].host_header is None
            else "https://" + redirect_info["repo_service"].host_header
        )
        base_url = urljoin(redirect_host, "login/oauth/authorize")
        state = self.generate_state()
        query = dict(
            response_type="code",
            scope=",".join(scope),
            client_id=redirect_info["client_id"],
            state=state,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    async def _get_teams_data(self, repo_service):
        # https://docs.github.com/en/rest/reference/teams#list-teams-for-the-authenticated-user
        teams = []
        if settings.IS_ENTERPRISE:
            async with repo_service.get_client() as client:
                try:
                    teams = []
                    curr_page = 1
                    while True:
                        curr_teams = await repo_service.api(
                            client, "get", f"/user/teams?per_page=100&page={curr_page}"
                        )
                        teams.extend(curr_teams)
                        curr_page += 1
                        if len(curr_teams) == 0:
                            break
                except TorngitError as exp:
                    log.error(f"Failed to get GitHub teams information: {exp}")
        return teams

    @async_to_sync
    async def fetch_user_data(self, code) -> Optional[dict]:
        # https://docs.github.com/en/rest/reference/teams#list-teams-for-the-authenticated-user
        # This is specific to GitHub
        repo_service = self.repo_service_instance
        authenticated_user = await repo_service.get_authenticated_user(code)
        if "access_token" not in authenticated_user:
            log.warning(
                "Missing access_token during GitHub OAuth",
                extra=dict(
                    user_info=authenticated_user,
                ),
            )
            return None
        # Comply to torngit's token encoding
        authenticated_user["key"] = authenticated_user["access_token"]
        user_orgs = await repo_service.list_teams()
        student_disabled = get_config(self.service, "student_disabled", default=False)
        if not student_disabled:
            is_student = await repo_service.is_student()
        else:
            is_student = False
        has_private_access = "repo" in authenticated_user["scope"].split(",")

        teams = await self._get_teams_data(repo_service)

        return dict(
            user=authenticated_user,
            orgs=user_orgs,
            teams=teams,
            is_student=is_student,
            has_private_access=has_private_access,
        )

    def actual_login_step(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        redirection_url = self.get_redirection_url_from_state(state)
        try:
            user_dict = self.fetch_user_data(code)
            if user_dict is None:
                return redirect(self.error_redirection_page)
        except TorngitError:
            log.warning("Unable to log in due to problem on Github", exc_info=True)
            return redirect(self.error_redirection_page)
        owner = self.get_and_modify_owner(user_dict, request)
        redirection_url = self.modify_redirection_url_based_on_default_user_org(
            redirection_url, owner
        )
        response = redirect(redirection_url)
        self.login_owner(owner, request, response)
        self.remove_state(state)
        self.store_access_token_expiry_to_cookie(response)
        return response

    def get(self, request):
        if settings.DISABLE_GIT_BASED_LOGIN and request.user.is_anonymous:
            return redirect(f"{settings.CODECOV_DASHBOARD_URL}/login")

        if request.GET.get("code"):
            return self.actual_login_step(request)
        else:
            scope = ["user:email", "read:org", "repo:status", "write:repo_hook"]
            if (
                settings.IS_ENTERPRISE
                or request.COOKIES.get("ghpr") == "true"
                or request.GET.get("private")
            ):
                log.info("Appending repo to scope")
                scope.append("repo")
                url_to_redirect_to = self.get_url_to_redirect_to(scope)
                response = redirect(url_to_redirect_to)
                seconds_in_one_year = 365 * 24 * 60 * 60
                domain_to_use = settings.COOKIES_DOMAIN
                response.set_cookie(
                    "ghpr",
                    "true",
                    max_age=seconds_in_one_year,
                    httponly=True,
                    domain=domain_to_use,
                )
                self.store_to_cookie_utm_tags(response)
                return response
            url_to_redirect_to = self.get_url_to_redirect_to(scope)
            response = redirect(url_to_redirect_to)
            self.store_to_cookie_utm_tags(response)
            return response

    # Set a session expiry of 8 hours for github logins. GH access tokens expire after 8 hours by default
    # https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/token-expiration-and-revocation#user-token-revoked-due-to-github-app-configuration
    def store_access_token_expiry_to_cookie(self, response):
        domain_to_use = settings.COOKIES_DOMAIN
        eight_hours_later = datetime.utcnow() + timedelta(hours=8)
        eight_hours_later_iso = eight_hours_later.isoformat() + "Z"
        response.set_cookie(
            "session_expiry", eight_hours_later_iso, domain=domain_to_use
        )
