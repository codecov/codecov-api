import logging

from codecov.commands.base import BaseInteractor
from services.repo_providers import RepoProviderService

log = logging.getLogger(__name__)


class GetFileContentInteractor(BaseInteractor):
    async def get_file_from_service(self, commit, path):
        try:
            repository_service = RepoProviderService().get_adapter(
                user=self.current_user, repo=commit.repository
            )
            content = await repository_service.get_source(path, commit.commitid)
            return content.get("content").decode("utf-8")
        # TODO raise this to the API so we can handle it.
        except Exception as e:
            log.info(
                "GetFileContentInteractor - exception raised",
                extra=dict(commitid=commit.commitid, path=path, error=e),
            )
            return None

    def execute(self, commit, path):
        return self.get_file_from_service(commit, path)
