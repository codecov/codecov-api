from django.db.models import Manager, Q, QuerySet


class CommitReportQuerySet(QuerySet):
    def coverage_reports(self):
        """
        Filters queryset such that only coverage reports are included.
        """
        return self.filter(Q(report_type=None) | Q(report_type="coverage"))


class CommitReportManager(Manager):
    def get_queryset(self):
        return CommitReportQuerySet(self.model, using=self._db)

    def coverage_reports(self, *args, **kwargs):
        return self.get_queryset().coverage_reports(*args, **kwargs)
