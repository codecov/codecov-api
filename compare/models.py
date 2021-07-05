from django.db import models

from codecov.models import BaseCodecovModel
from core.models import Commit


class CommitComparison(BaseCodecovModel):
    class CommitComparisonStates(models.TextChoices):
        PENDING = "pending"
        ERROR = "error"
        PROCESSED = "processed"

    base_commit = models.ForeignKey(
        Commit, on_delete=models.CASCADE, related_name="base_commit_comparisons"
    )
    compare_commit = models.ForeignKey(
        Commit, on_delete=models.CASCADE, related_name="compare_commit_comparisons"
    )
    state = models.TextField(
        choices=CommitComparisonStates.choices, default=CommitComparisonStates.PENDING
    )
    report_storage_path = models.CharField(max_length=150, null=True)
