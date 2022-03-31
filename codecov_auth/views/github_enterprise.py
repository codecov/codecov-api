import logging
from urllib.parse import urlencode, urljoin

from asgiref.sync import async_to_sync
from django.conf import settings
from shared.torngit import GithubEnterprise

from .github import GithubLoginView

log = logging.getLogger(__name__)


class GitHubEnterpriseLoginView(GithubLoginView):
    service = "github_enterprise"
    error_redirection_page = "/"

    def get_url_to_redirect_to(self, scope):
        repo_service = GithubEnterprise()
        base_url = urljoin(repo_service.service_url, "login/oauth/authorize")
        state = self.generate_state()
        query = dict(
            response_type="code",
            scope=",".join(scope),
            client_id=settings.GITHUB_ENTERPRISE_CLIENT_ID,
            state=state,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    @async_to_sync
    async def fetch_user_data(self, code):
        repo_service = GithubEnterprise(
            oauth_consumer_token=dict(
                key=settings.GITHUB_ENTERPRISE_CLIENT_ID,
                secret=settings.GITHUB_ENTERPRISE_CLIENT_SECRET,
            )
        )
        authenticated_user = await repo_service.get_authenticated_user(code)
        user_orgs = await repo_service.list_teams()
        is_student = await repo_service.is_student()
        has_private_access = "repo" in authenticated_user["scope"].split(",")
        return dict(
            user=authenticated_user,
            orgs=user_orgs,
            is_student=is_student,
            has_private_access=has_private_access,
        )
