from codecov.commands.base import BaseInteractor
from codecov_auth.models import RepositoryToken
from asgiref.sync import sync_to_async

class GetProfilingTokenInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository):
        token = RepositoryToken.objects.filter(
        repository_id=repository.repoid, token_type='profiling').first()
        if token:
            return token.key

