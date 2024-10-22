from django.db.models import Prefetch

from core.models import Commit
from reports.models import CommitReport

from .loader import BaseLoader


class CommitLoader(BaseLoader):
    @classmethod
    def key(cls, commit):
        return commit.commitid

    def __init__(self, info, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        super().__init__(info, *args, **kwargs)

    def batch_queryset(self, keys):
        # We don't select the `report` column here b/c then can be
        # very large JSON blobs and cause performance issues

        # prefetch the CommitReport with the ReportLevelTotals
        prefetch = Prefetch(
            "reports",
            queryset=CommitReport.objects.coverage_reports()
            .filter(code=None)
            .select_related("reportleveltotals"),
        )

        return (
            Commit.objects.filter(commitid__in=keys, repository_id=self.repository_id)
            .defer("_report")
            .prefetch_related(prefetch)
        )
