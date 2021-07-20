from codecov.commands.base import BaseCommand

from .interactors.fetch_branch import FetchBranchInteractor


class BranchCommands(BaseCommand):
    def fetch_branch(self, repository, branch_name):
        return self.get_interactor(FetchBranchInteractor).execute(
            repository, branch_name
        )
