from django.conf import settings

import services.self_hosted as self_hosted
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import (
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov_auth.models import Owner
from core.models import Repository
from services.task import TaskService


class DeleteComponentMeasurementsInteractor(BaseInteractor):
    def validate(self, owner: Owner, repo: Repository):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if not owner:
            raise ValidationError("Owner not found")

        if not repo:
            raise ValidationError("Repo not found")

        if settings.IS_ENTERPRISE:
            if not self_hosted.is_admin_owner(self.current_owner):
                raise Unauthorized()
        else:
            if not owner.is_admin(self.current_owner):
                raise Unauthorized()

    def execute(self, owner_username: str, repo_name: str, component_id: str):
        owner = Owner.objects.filter(
            service=self.service, username=owner_username
        ).first()

        repo = None
        if owner:
            repo = Repository.objects.filter(author_id=owner.pk, name=repo_name).first()

        self.validate(owner, repo)

        TaskService().delete_component_measurements(
            repo.repoid,
            component_id,
        )
