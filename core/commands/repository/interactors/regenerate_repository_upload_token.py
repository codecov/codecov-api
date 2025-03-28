import uuid

from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class RegenerateRepositoryUploadTokenInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repo_name: str, owner_username: str) -> uuid.UUID:
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, only_viewable=True
        )

        repo.upload_token = uuid.uuid4()
        repo.save()
        return repo.upload_token
