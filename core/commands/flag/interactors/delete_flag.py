from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.models import Owner
from core.models import Repository
from reports.models import RepositoryFlag


class DeleteFlagInteractor(BaseInteractor):
    def validate(self, owner: Owner, repo: Repository):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if not owner:
            raise ValidationError("Owner not found")

        if not repo:
            raise ValidationError("Repo not found")

        if not owner.is_admin(self.current_user):
            raise Unauthorized()

    def execute(self, owner_username: str, repo_name: str, flag_name: str):
        owner = Owner.objects.filter(
            service=self.service, username=owner_username
        ).first()

        repo = None
        if owner:
            repo = Repository.objects.filter(author_id=owner.pk, name=repo_name).first()

        self.validate(owner, repo)

        flag = RepositoryFlag.objects.filter(
            repository_id=repo.pk, flag_name=flag_name
        ).first()
        if not flag:
            return

        flag.deleted = True
        flag.save()
