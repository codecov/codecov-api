from django.db import models

from codecov.models import BaseCodecovModel
from core.models import Commit


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
            ),
        ]
