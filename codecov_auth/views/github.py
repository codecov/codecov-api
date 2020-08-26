import asyncio

from django.shortcuts import redirect
from shared.torngit import Github
from urllib.parse import urljoin, urlencode
from django.views import View
from django.conf import settings
from codecov_auth.views.base import LoginMixin


class GithubLoginView(View, LoginMixin):
    def get_is_enterprise(self):
        return False

    def get_url_to_redirect_to(self, scope):
        repo_service = Github
        base_url = urljoin(repo_service.service_url, "login/oauth/authorize")
        query = dict(
            response_type="code",
            scope=",".join(scope),
            client_id=settings.GITHUB_CLIENT_ID,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    def get_github_authorized_user(self, code):
        repo_service = Github(
            oauth_consumer_token=dict(
                key=settings.GITHUB_CLIENT_ID, secret=settings.GITHUB_CLIENT_SECRET
            )
        )
        data = asyncio.run(repo_service.get_authenticated_user(code))
        self.backfill_github_specific_information(repo_service, data)
        return {
            "service_id": data["id"],
            "username": data["login"],
            "access_token": data["access_token"],
        }

    def backfill_github_specific_information(self, repo_service, data):
        pass

    def get(self, request):
        if request.GET.get("code"):
            user_dict = self.get_github_authorized_user(request.GET.get("code"))
            response = redirect("/redirect_app")
            self.login_from_user_dict(user_dict, request, response)
            return response
        else:
            scope = ["user:email", "read:org", "repo:status", "write:repo_hook"]
            if self.get_is_enterprise() or request.COOKIES.get("ghpr") == "true":
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
                return response
            url_to_redirect_to = self.get_url_to_redirect_to(scope)
            response = redirect(url_to_redirect_to)
            return response
