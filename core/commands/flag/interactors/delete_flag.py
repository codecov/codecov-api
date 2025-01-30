from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import (
    NotFound,
)
from reports.models import RepositoryFlag


class DeleteFlagInteractor(BaseInteractor):
    def execute(self, owner_username: str, repo_name: str, flag_name: str):
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, ensure_is_admin=True
        )

        flag = RepositoryFlag.objects.filter(
            repository_id=repo.pk, flag_name=flag_name
        ).first()
        if not flag:
            raise NotFound()

        flag.deleted = True
        flag.save()
