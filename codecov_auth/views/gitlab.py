import asyncio
from django.urls import reverse
from uuid import uuid4

from django.shortcuts import redirect
from shared.torngit import Gitlab
from urllib.parse import urljoin, urlencode
from django.views import View
from django.conf import settings
from codecov_auth.views.base import LoginMixin


class GitlabLoginView(View, LoginMixin):
    cookie_prefix = "gitlab"

    def get_url_to_redirect_to(self):
        repo_service = Gitlab
        base_url = urljoin(repo_service.service_url, "oauth/authorize")
        redirect_uri = settings.GITLAB_REDIRECT_URI
        query = dict(
            response_type="code",
            client_id=settings.GITLAB_CLIENT_ID,
            redirect_uri=redirect_uri,
            state=uuid4().hex,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    async def fetch_user_data(self, request, code):
        redirect_uri = request.build_absolute_uri(reverse("gitlab-login"))
        repo_service = Gitlab(
            oauth_consumer_token=dict(
                key=settings.GITLAB_CLIENT_ID, secret=settings.GITLAB_CLIENT_SECRET
            )
        )
        user_dict = await repo_service.get_authenticated_user(code, redirect_uri)
        user_dict["login"] = user_dict["username"]
        user_orgs = await repo_service.list_teams()
        return dict(user=user_dict, orgs=user_orgs)

    def get(self, request):
        if request.GET.get("code"):
            code = request.GET.get("code")
            user_dict = user_dict = asyncio.run(self.fetch_user_data(request, code))
            response = redirect("/gl")
            self.login_from_user_dict(user_dict, request, response)
            return response
        else:
            url_to_redirect_to = self.get_url_to_redirect_to()
            response = redirect(url_to_redirect_to)
            return response
