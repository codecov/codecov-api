from codecov.commands.base import BaseCommand

from .interactors.change_with_parent import ChangeWithParentInteractor
from .interactors.get_impacted_files import GetImpactedFilesInteractor


class CompareCommands(BaseCommand):
    def get_impacted_files(self, comparison):
        return self.get_interactor(GetImpactedFilesInteractor).execute(comparison)

    async def change_with_parent(self, comparison):
        current_commit_totals = await self.get_command("commit").fetch_totals(
            comparison.compare_commit
        )
        parent_commit_totals = await self.get_command("commit").fetch_totals(
            comparison.base_commit
        )

        if not current_commit_totals or not parent_commit_totals:
            return None

        return await self.get_interactor(ChangeWithParentInteractor).execute(
            current_commit_totals, parent_commit_totals
        )
