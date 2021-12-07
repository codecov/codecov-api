from django.db import models

from codecov.models import BaseCodecovModel

# Create your models here.


class ProfilingCommit(BaseCodecovModel):
    last_joined_uploads_at = models.DateTimeField(null=True)
    environment = models.CharField(max_length=100, null=True)
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
    commit_sha = models.TextField(null=True)
    code = models.TextField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "code"], name="uniquerepocode"
            )
        ]

    def __str__(self):
        return f"ProfilingCommit<{self.version_identifier} at {self.repository}>"


class ProfilingUpload(BaseCodecovModel):
    raw_upload_location = models.TextField()
    profiling_commit = models.ForeignKey(
        ProfilingCommit, on_delete=models.CASCADE, related_name="uploads",
    )
    normalized_at = models.DateTimeField(null=True)
    normalized_location = models.TextField(null=True)
