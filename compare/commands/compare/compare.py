from codecov.commands.base import BaseCommand

from .interactors.compare_commits import CompareCommitInteractor


class CompareCommands(BaseCommand):
    def compare_commit_with_parent(self, commit):
        parent_commit = commit.parent_commit
        return self.get_interactor(CompareCommitInteractor).execute(
            commit, parent_commit
        )
