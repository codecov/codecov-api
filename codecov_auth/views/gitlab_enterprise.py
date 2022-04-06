import logging
from urllib.parse import urlencode, urljoin

from asgiref.sync import async_to_sync
from django.conf import settings
from shared.torngit import GitlabEnterprise

from .gitlab import GitlabLoginView

log = logging.getLogger(__name__)


class GitlabEnterpriseLoginView(GitlabLoginView):
    service = "gitlab_enterprise"
    error_redirection_page = "/"

    def get_url_to_redirect_to(self):
        repo_service = GitlabEnterprise()
        base_url = urljoin(repo_service.service_url, "oauth/authorize")
        state = self.generate_state()
        redirect_uri = settings.GITLAB_ENTERPRISE_REDIRECT_URI
        query = dict(
            response_type="code",
            client_id=settings.GITLAB_ENTERPRISE_CLIENT_ID,
            redirect_uri=redirect_uri,
            state=state,
        )
        query_str = urlencode(query)
        return f"{base_url}?{query_str}"

    @async_to_sync
    async def fetch_user_data(self, request, code):
        redirect_uri = settings.GITLAB_ENTERPRISE_REDIRECT_URI
        repo_service = GitlabEnterprise(
            oauth_consumer_token=dict(
                key=settings.GITLAB_ENTERPRISE_CLIENT_ID,
                secret=settings.GITLAB_ENTERPRISE_CLIENT_SECRET,
            )
        )
        user_dict = await repo_service.get_authenticated_user(code, redirect_uri)
        user_dict["login"] = user_dict["username"]
        user_orgs = await repo_service.list_teams()
        return dict(
            user=user_dict, orgs=user_orgs, is_student=False, has_private_access=True
        )
