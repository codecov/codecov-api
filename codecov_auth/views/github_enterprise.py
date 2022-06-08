import logging

from django.conf import settings
from shared.torngit import GithubEnterprise

from .github import GithubLoginView

log = logging.getLogger(__name__)


class GithubEnterpriseLoginView(GithubLoginView):
    service = "github_enterprise"
    error_redirection_page = "/"

    @property
    def repo_service_instance(self):
        return GithubEnterprise(
            oauth_consumer_token=dict(
                key=settings.GITHUB_ENTERPRISE_CLIENT_ID,
                secret=settings.GITHUB_ENTERPRISE_CLIENT_SECRET,
            )
        )

    @property
    def redirect_info(self):
        return dict(
            repo_service=GithubEnterprise(),
            client_id=settings.GITHUB_ENTERPRISE_CLIENT_ID,
        )
