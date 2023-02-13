from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async


class FetchBranchInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, branch_name):
        return repository.branches.filter(name=branch_name).first()
