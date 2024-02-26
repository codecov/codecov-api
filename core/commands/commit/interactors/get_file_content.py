import logging

from codecov.commands.base import BaseInteractor
from services.repo_providers import RepoProviderService

log = logging.getLogger(__name__)


class GetFileContentInteractor(BaseInteractor):
    async def get_file_from_service(self, commit, path):
        try:
            repository_service = await RepoProviderService().async_get_adapter(
                owner=self.current_owner, repo=commit.repository
            )
            content = await repository_service.get_source(path, commit.commitid)
            # Sometimes the content may be of type str, so don't decode it
            if type(content.get("content")) == str:
                return content.get("content")
            return content.get("content").decode("utf-8")
        # TODO raise this to the API so we can handle it.
        except Exception:
            log.exception(
                "GetFileContentInteractor - exception raised",
                extra=dict(commitid=commit.commitid),
            )
            return None

    def execute(self, commit, path):
        return self.get_file_from_service(commit, path)
