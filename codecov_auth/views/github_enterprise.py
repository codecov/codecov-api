import logging
from urllib.parse import urlencode, urljoin

from asgiref.sync import async_to_sync
from django.conf import settings
from shared.torngit import GithubEnterprise

from .github import GithubLoginView

log = logging.getLogger(__name__)


class GithubEnterpriseLoginView(GithubLoginView):
    service = "github_enterprise"
    error_redirection_page = "/"

    @property
    def get_repo_service_instance(self):
        return GithubEnterprise(
            oauth_consumer_token=dict(
                key=settings.GITHUB_ENTERPRISE_CLIENT_ID,
                secret=settings.GITHUB_ENTERPRISE_CLIENT_SECRET,
            )
        )

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
