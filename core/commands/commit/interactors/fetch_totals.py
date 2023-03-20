from django.db.models import Prefetch

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from reports.models import CommitReport


class FetchTotalsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        if commit.commitreport and hasattr(commit.commitreport, "reportleveltotals"):
            return commit.commitreport.reportleveltotals
