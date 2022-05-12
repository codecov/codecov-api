from codecov.commands.base import BaseInteractor
from codecov_auth.models import RepositoryToken
from core.models import Repository
from asgiref.sync import sync_to_async
from codecov.commands.exceptions import Unauthenticated, ValidationError

class RegenerateProfilingTokenInteractor(BaseInteractor):
    def validate(self):
        print(self.current_user)
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, repoName):
        self.validate()
        repo = Repository.objects.filter(name=repoName).first()
        if repo:
            token = RepositoryToken.objects.filter(
            repository_id=repo.repoid, token_type='profiling').first()
            if token:
                token.key = token.generate_key()
                token.save()
                return token.key

