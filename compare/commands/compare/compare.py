from codecov.commands.base import BaseCommand

from .interactors.compare_commits import CompareCommitsInteractor
from .interactors.get_impacted_files import GetImpactedFilesInteractor


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

    async def compare_pull_request(self, pull):
        head_commit = await self.get_command("commit").fetch_commit(
            pull.repository, pull.head
        )
        base_commit = await self.get_command("commit").fetch_commit(
            pull.repository, pull.compared_to
        )
        return await self.get_interactor(CompareCommitsInteractor).execute(
            head_commit, base_commit
        )

    def get_impacted_files(self, comparison):
        return self.get_interactor(GetImpactedFilesInteractor).execute(comparison)
