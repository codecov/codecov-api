from codecov.commands.base import BaseInteractor
from services.task import TaskService


class DeleteComponentMeasurementsInteractor(BaseInteractor):
    def execute(self, owner_username: str, repo_name: str, component_id: str):
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, ensure_is_admin=True
        )

        TaskService().delete_component_measurements(
            repo.repoid,
            component_id,
        )
