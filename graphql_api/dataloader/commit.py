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
        return super().__init__(info, *args, **kwargs)

    def batch_queryset(self, keys):
        # We don't select the `report` or `files_array` columns here b/c then can be
        # very large JSON blobs and cause performance issues

        # prefetch the CommitReport with the ReportLevelTotals and ReportDetails
        prefetch = Prefetch(
            "reports",
            queryset=CommitReport.objects.select_related(
                "reportleveltotals", "reportdetails"
            ).defer("reportdetails__files_array"),
        )

        return (
            Commit.objects.filter(commitid__in=keys, repository_id=self.repository_id)
            .defer("report")
            .prefetch_related(prefetch)
        )
