import uuid

from django.db import models
from django.contrib.postgres.fields import ArrayField


# Create your models here.


class BaseCodecovModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    external_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AbstractTotals(BaseCodecovModel):
    branches = models.IntegerField()
    coverage = models.DecimalField(max_digits=7, decimal_places=2)
    hits = models.IntegerField()
    lines = models.IntegerField()
    methods = models.IntegerField()
    misses = models.IntegerField()
    partials = models.IntegerField()
    files = models.IntegerField()

    class Meta:
        abstract = True


class CommitReport(BaseCodecovModel):
    commit = models.ForeignKey(
        "core.Commit", related_name="reports", on_delete=models.CASCADE,
    )


class ReportDetails(BaseCodecovModel):
    report = models.OneToOneField(CommitReport, on_delete=models.CASCADE)
    files_array = ArrayField(models.JSONField())


class ReportLevelTotals(AbstractTotals):
    report = models.OneToOneField(CommitReport, on_delete=models.CASCADE)


class ReportSessionError(BaseCodecovModel):
    report_session = models.ForeignKey(
        "ReportSession", db_column="upload_id", related_name="errors", on_delete=models.CASCADE,
    )
    error_code = models.CharField(max_length=100)
    error_params = models.JSONField(default=dict)

    class Meta:
        db_table = "reports_uploaderror"


class ReportSessionFlagMembership(models.Model):
    report_session = models.ForeignKey("ReportSession", db_column="upload_id", on_delete=models.CASCADE)
    flag = models.ForeignKey("RepositoryFlag", on_delete=models.CASCADE)
    id = models.BigAutoField(primary_key=True)

    class Meta:
        db_table = "reports_uploadflagmembership"


class RepositoryFlag(BaseCodecovModel):
    repository = models.ForeignKey(
        "core.Repository", related_name="flags", on_delete=models.CASCADE,
    )
    flag_name = models.CharField(max_length=255)


class ReportSession(BaseCodecovModel):
    build_code = models.TextField(null=True)
    build_url = models.TextField(null=True)
    env = models.JSONField(null=True)
    flags = models.ManyToManyField(RepositoryFlag, through=ReportSessionFlagMembership)
    job_code = models.TextField(null=True)
    name = models.CharField(null=True, max_length=100)
    provider = models.CharField(max_length=50, null=True)
    report = models.ForeignKey(
        "CommitReport", related_name="sessions", on_delete=models.CASCADE,
    )
    state = models.CharField(max_length=100)
    storage_path = models.TextField()
    order_number = models.IntegerField(null=True)

    class Meta:
        db_table = "reports_upload"


class SessionLevelTotals(AbstractTotals):
    report_session = models.OneToOneField(ReportSession, db_column="upload_id", on_delete=models.CASCADE)

    class Meta:
        db_table = "reports_uploadleveltotals"