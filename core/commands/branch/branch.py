from codecov.commands.base import BaseCommand


class BranchCommands(BaseCommand):
    def fetch_branch(self, repository, commit_id):
        return self.get_interactor().execute(repository, commit_id)
