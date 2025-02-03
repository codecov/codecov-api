from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from services.task.task import TaskService


class EraseRepositoryInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner_username: str, repo_name: str) -> None:
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, ensure_is_admin=True
        )

        TaskService().delete_timeseries(repository_id=repo.repoid)
        TaskService().flush_repo(repository_id=repo.repoid)
