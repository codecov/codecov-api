import logging

from django.conf import settings
from shared.torngit import GitlabEnterprise

from .gitlab import GitlabLoginView

log = logging.getLogger(__name__)


class GitlabEnterpriseLoginView(GitlabLoginView):
    service = "gitlab_enterprise"
    error_redirection_page = "/"

    @property
    def repo_service_instance(self):
        return GitlabEnterprise(
            oauth_consumer_token=dict(
                key=settings.GITLAB_ENTERPRISE_CLIENT_ID,
                secret=settings.GITLAB_ENTERPRISE_CLIENT_SECRET,
            )
        )

    @property
    def redirect_info(self):
        return dict(
            redirect_uri=settings.GITLAB_ENTERPRISE_REDIRECT_URI,
            repo_service=GitlabEnterprise(),
            client_id=settings.GITLAB_ENTERPRISE_CLIENT_ID,
        )
