from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor

class ChangeWithParentInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, current_commit_totals, parent_commit_totals):
        if not current_commit_totals or not parent_commit_totals:
            return None

        if not hasattr(current_commit_totals, "coverage") or not hasattr(parent_commit_totals, "coverage"):
            return None

        return current_commit_totals.coverage - parent_commit_totals.coverage
