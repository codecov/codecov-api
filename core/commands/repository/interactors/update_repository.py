from typing import Optional

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner
from core.models import Repository


class UpdateRepositoryInteractor(BaseInteractor):
    def validate_owner(self, owner: Owner):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if not current_user_part_of_org(self.current_owner, owner):
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
