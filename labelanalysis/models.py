from django.contrib.postgres.fields import ArrayField
from django.db import models
from shared.labelanalysis import LabelAnalysisRequestState

from codecov.models import BaseCodecovModel


class LabelAnalysisRequest(BaseCodecovModel):
    base_commit = models.ForeignKey(
        "core.Commit", on_delete=models.CASCADE, related_name="label_requests_as_base"
    )
    head_commit = models.ForeignKey(
        "core.Commit", on_delete=models.CASCADE, related_name="label_requests_as_head"
    )
    requested_labels = ArrayField(models.TextField(), null=True)
    state_id = models.IntegerField(
        null=False, choices=LabelAnalysisRequestState.choices()
    )
    result = models.JSONField(null=True)
    processing_params = models.JSONField(null=True)
