import asyncio
import logging
from urllib.parse import urlencode, urljoin
from uuid import uuid4

from asgiref.sync import async_to_sync
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from shared.torngit import Gitlab
from shared.torngit.exceptions import TorngitError

from codecov_auth.views.base import LoginMixin, StateMixin

log = logging.getLogger(__name__)


class GitlabLoginView(LoginMixin, StateMixin, View):
    service = "gitlab"
    error_redirection_page = "/"

    def get_url_to_redirect_to(self):
        repo_service = Gitlab
        base_url = urljoin(repo_service.service_url, "oauth/authorize")
        state = self.generate_state()
        redirect_uri = settings.GITLAB_REDIRECT_URI
        query = dict(
            response_type="code",
            client_id=settings.GITLAB_CLIENT_ID,
            redirect_uri=redirect_uri,
            state=state,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    @async_to_sync
    async def fetch_user_data(self, request, code):
        redirect_uri = settings.GITLAB_REDIRECT_URI
        repo_service = Gitlab(
            oauth_consumer_token=dict(
                key=settings.GITLAB_CLIENT_ID, secret=settings.GITLAB_CLIENT_SECRET
            )
        )
        user_dict = await repo_service.get_authenticated_user(code, redirect_uri)
        user_dict["login"] = user_dict["username"]
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
        redirection_url = self.get_redirection_url_from_state(state)
        response = redirect(redirection_url)
        self.login_from_user_dict(user_dict, request, response)
        self.remove_state(state, delay=5)
        return response

    def get(self, request):
        if request.GET.get("code"):
            return self.actual_login_step(request)
        else:
            url_to_redirect_to = self.get_url_to_redirect_to()
            response = redirect(url_to_redirect_to)
            return response
