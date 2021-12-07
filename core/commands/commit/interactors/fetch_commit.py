from asgiref.sync import sync_to_async
from django.db.models import Prefetch

from codecov.commands.base import BaseInteractor
from core.models import Commit
from reports.models import CommitReport


class FetchCommitInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, commit_id):
        # prefetch the CommitReport with the ReportLevelTotals
        prefetch = Prefetch(
            "reports", queryset=CommitReport.objects.select_related("reportleveltotals")
        )
        return (
            repository.commits.prefetch_related(prefetch)
            .filter(commitid=commit_id)
            .first()
        )
