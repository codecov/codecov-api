from codecov.commands.base import BaseInteractor
from codecov_auth.models import RepositoryToken, Owner
from asgiref.sync import sync_to_async
from codecov.commands.exceptions import Unauthenticated, ValidationError
from core.models import Repository

class RegenerateProfilingTokenInteractor(BaseInteractor):
    def validate(self, repo):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not repo:
             raise ValidationError(
                    "Repo not found"
                )

    @sync_to_async
    def execute(self, repoName, owner):
        author = Owner.objects.filter(name=owner, service=self.service).first()
        repo =  Repository.objects.viewable_repos(self.current_user).filter(author=author, name=repoName).first()
        self.validate(repo)

        token = RepositoryToken.objects.filter(
        repository_id=repo.repoid, token_type='profiling').first()
        if token:
            token.key = token.generate_key()
            token.save()
            return token.key

