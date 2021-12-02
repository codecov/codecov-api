from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class ChangeWithParentInteractor(BaseInteractor):
    def change_coverage(self, commit_totals, compare_to_totals):
        return commit_totals.coverage - compare_to_totals.coverage

    @sync_to_async
    def execute(self, current_commit_totals, parent_commit_totals):
        if not hasattr(current_commit_totals, "coverage") or not hasattr(
            parent_commit_totals, "coverage"
        ):
            return None

        return self.change_coverage(current_commit_totals, parent_commit_totals)
