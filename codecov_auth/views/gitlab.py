import asyncio
from django.urls import reverse

from django.shortcuts import redirect
from shared.torngit import Gitlab
from urllib.parse import urljoin, urlencode
from django.views import View
from django.conf import settings
from codecov_auth.views.base import LoginMixin


class GitlabLoginView(View, LoginMixin):
    cookie_prefix = "gitlab"

    def get_url_to_redirect_to(self, request):
        repo_service = Gitlab
        base_url = urljoin(repo_service.service_url, "oauth/authorize")
        redirect_uri = request.build_absolute_uri(reverse("gitlab-login"))
        query = dict(
            response_type="code",
            client_id=settings.GITLAB_CLIENT_ID,
            redirect_uri=redirect_uri,
            state="aaaaa"
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    def get_gitlab_authorized_user(self, request, code):
        repo_service = Gitlab(
            oauth_consumer_token=dict(
                key=settings.GITLAB_CLIENT_ID, secret=settings.GITLAB_CLIENT_SECRET
            )
        )
        redirect_uri = request.build_absolute_uri(reverse("gitlab-login"))
        data = asyncio.run(repo_service.get_authenticated_user(code, redirect_uri))
        self.backfill_gitlab_specific_information(repo_service, data)
        return {
            "service_id": data["id"],
            "username": data["username"],
            "access_token": data["access_token"],
        }

    def backfill_gitlab_specific_information(self, repo_service, data):
        pass

    def get(self, request):
        if request.GET.get("code"):
            user_dict = self.get_gitlab_authorized_user(request, request.GET.get("code"))
            response = redirect("/redirect_app")
            self.login_from_user_dict(user_dict, request, response)
            return response
        else:
            url_to_redirect_to = self.get_url_to_redirect_to(request)
            response = redirect(url_to_redirect_to)
            return response
