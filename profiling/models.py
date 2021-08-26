from django.db import models
from codecov.models import BaseCodecovModel
# Create your models here.


class ProfilingCommit(BaseCodecovModel):
    last_joined_uploads_at = models.DateTimeField(null=True)
    last_summarized_at = models.DateTimeField(null=True)
    joined_location = models.TextField(null=True)
    summarized_location = models.TextField(null=True)
    version_identifier = models.TextField()
    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="profilings",
    )


class ProfilingUpload(BaseCodecovModel):
    raw_upload_location = models.TextField()
    profiling_commit = models.ForeignKey(
        ProfilingCommit, on_delete=models.CASCADE, related_name="uploads",
    )
    normalized_at = models.DateTimeField(null=True)
    normalized_location = models.TextField(null=True)
