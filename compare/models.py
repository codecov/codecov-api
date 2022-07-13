import pytz
from django.db import models

from codecov.models import BaseCodecovModel
from core.models import Commit
from reports.models import RepositoryFlag


class CommitComparison(BaseCodecovModel):
    class CommitComparisonStates(models.TextChoices):
        PENDING = "pending"
        ERROR = "error"
        PROCESSED = "processed"

    class CommitComparisonErrors(models.TextChoices):
        MISSING_BASE_REPORT = "missing_base_report"
        MISSING_HEAD_REPORT = "missing_head_report"

    base_commit = models.ForeignKey(
        Commit, on_delete=models.CASCADE, related_name="base_commit_comparisons"
    )
    compare_commit = models.ForeignKey(
        Commit, on_delete=models.CASCADE, related_name="compare_commit_comparisons"
    )
    state = models.TextField(
        choices=CommitComparisonStates.choices, default=CommitComparisonStates.PENDING
    )
    error = models.TextField(choices=CommitComparisonErrors.choices, null=True)
    report_storage_path = models.CharField(max_length=150, null=True, blank=True)
    patch_totals = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_comparison_between_commit",
                fields=["base_commit", "compare_commit"],
            )
        ]

    @property
    def is_processed(self):
        return self.state == CommitComparison.CommitComparisonStates.PROCESSED

    @property
    def needs_recalculation(self):
        timezone = pytz.utc
        return (
            self.compare_commit.updatestamp
            and timezone.normalize(self.updated_at)
            < timezone.localize(self.compare_commit.updatestamp)
        ) or (
            self.base_commit.updatestamp
            and timezone.normalize(self.updated_at)
            < timezone.localize(self.base_commit.updatestamp)
        )


class FlagComparison(BaseCodecovModel):
    commit_comparison = models.ForeignKey(
        CommitComparison, on_delete=models.CASCADE, related_name="flag_comparisons"
    )
    repositoryflag = models.ForeignKey(
        RepositoryFlag, on_delete=models.CASCADE, related_name="flag_comparisons"
    )
    coverage_totals = models.JSONField(null=True)
    patch_totals = models.JSONField(null=True)
