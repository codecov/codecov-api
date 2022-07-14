from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Owner, RepositoryToken
from core.models import Repository


class RegenerateProfilingTokenInteractor(BaseInteractor):
    def validate(self, repo):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not repo:
            raise ValidationError("Repo not found")

    @sync_to_async
    def execute(self, repo_name, owner):
        author = Owner.objects.filter(name=owner, service=self.service).first()
        repo = (
            Repository.objects.viewable_repos(self.current_user)
            .filter(author=author, name=repo_name, active=True)
            .first()
        )
        self.validate(repo)

        token, created = RepositoryToken.objects.get_or_create(
            repository_id=repo.repoid, token_type="profiling"
        )
        if not created:
            token.key = token.generate_key()
            token.save()
        return token.key
