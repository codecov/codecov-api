from codecov.commands.base import BaseCommand

from .interactors.fetch_branch import FetchBranchInteractor
from .interactors.fetch_branches import FetchRepoBranchesInteractor


class BranchCommands(BaseCommand):
    def fetch_branch(self, repository, branch_name):
        return self.get_interactor(FetchBranchInteractor).execute(
            repository, branch_name
        )

    def fetch_branches(self, repository):
        return self.get_interactor(FetchRepoBranchesInteractor).execute(repository)
