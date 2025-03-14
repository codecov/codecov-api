from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class FetchBranchInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, branch_name):
        return repository.branches.filter(name=branch_name).first()
