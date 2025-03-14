from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class FetchTotalsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        if commit.commitreport and hasattr(commit.commitreport, "reportleveltotals"):
            return commit.commitreport.reportleveltotals
