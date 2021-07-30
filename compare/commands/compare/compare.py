from codecov.commands.base import BaseCommand

from .interactors.compare_commits import CompareCommitsInteractor


class CompareCommands(BaseCommand):
    async def compare_commit_with_parent(self, commit):
        parent_commit = await self.get_command("commit").fetch_commit(
            commit.repository, commit.parent_commit_id
        )
        if not parent_commit:
            return None
        return await self.get_interactor(CompareCommitsInteractor).execute(
            commit, parent_commit
        )
