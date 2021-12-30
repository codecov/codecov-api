from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class FetchRepoBranchesInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository):
        return repository.branches.all()
