from typing import Optional

from django.conf import settings

import services.self_hosted as self_hosted
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.models import Repository


class UpdateRepositoryInteractor(BaseInteractor):
    def validate_owner(self, owner: Owner):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if settings.IS_ENTERPRISE:
            if not self_hosted.is_admin_owner(self.current_owner):
                raise Unauthorized()
        else:
            if not owner.is_admin(self.current_owner):
                raise Unauthorized()

    @sync_to_async
    def execute(
        self,
        repo_name: str,
        owner: Owner,
        default_branch: Optional[str],
        activated: Optional[bool],
    ):
        self.validate_owner(owner)
        repo = Repository.objects.filter(author_id=owner.pk, name=repo_name).first()
        if not repo:
            raise ValidationError("Repo not found")

        if default_branch:
            branch = repo.branches.filter(name=default_branch).first()
            if branch is None:
                raise ValidationError(
                    f"The branch '{default_branch}' is not in our records. Please provide a valid branch name.",
                )

            repo.branch = default_branch
        if activated:
            repo.activated = activated
        repo.save()
