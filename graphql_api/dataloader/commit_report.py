from reports.models import CommitReport

from .loader import BaseLoader


class CommitReportLoader(BaseLoader):
    @classmethod
    def key(cls, commit_report):
        return commit_report.commit_id

    def batch_queryset(self, keys):
        return CommitReport.objects.filter(commit__id__in=keys).select_related(
            "reportleveltotals"
        )
