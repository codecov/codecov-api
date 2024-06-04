from django.conf import settings

import services.self_hosted as self_hosted
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner
from core.models import Repository
from services.task.task import TaskService


class EraseRepositoryInteractor(BaseInteractor):
    def validate_owner(self, owner: Owner):
        if not current_user_part_of_org(self.current_owner, owner):
            raise Unauthorized()

        if settings.IS_ENTERPRISE:
            if not self_hosted.is_admin_owner(self.current_owner):
                raise Unauthorized()
        else:
            if not owner.is_admin(self.current_owner):
                raise Unauthorized()

    @sync_to_async
    def execute(self, repo_name: str, owner: Owner):
        self.validate_owner(owner)
        repo = Repository.objects.filter(author_id=owner.pk, name=repo_name).first()
        if not repo:
            raise ValidationError("Repo not found")
        TaskService().delete_timeseries(repository_id=repo.repoid)
        TaskService().flush_repo(repository_id=repo.repoid)
