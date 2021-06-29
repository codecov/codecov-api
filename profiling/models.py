import uuid

from django.db import models

# Create your models here.


class MixinBaseClass(models.Model):
    id = models.BigAutoField(primary_key=True)
    external_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProfilingCommit(MixinBaseClass):
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
    commit_sha = models.TextField(null=True)


class ProfilingUpload(MixinBaseClass):
    raw_upload_location = models.TextField()
    profiling_commit = models.ForeignKey(
        ProfilingCommit, on_delete=models.CASCADE, related_name="uploads",
    )
