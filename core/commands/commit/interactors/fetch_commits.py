from asgiref.sync import sync_to_async
from codecov.commands.base import BaseInteractor

class FetchCommitsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository):
        return repository.commits.all()