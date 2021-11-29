import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from shared.reports.enums import UploadState, UploadType

from codecov.models import BaseCodecovModel
from upload.constants import ci
from utils.services import get_short_service_name


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


class UploadError(BaseCodecovModel):
    report_session = models.ForeignKey(
        "ReportSession",
        db_column="upload_id",
        related_name="errors",
        on_delete=models.CASCADE,
    )
    error_code = models.CharField(max_length=100)
    error_params = models.JSONField(default=dict)

    class Meta:
        db_table = "reports_uploaderror"


class UploadFlagMembership(models.Model):
    report_session = models.ForeignKey(
        "ReportSession", db_column="upload_id", on_delete=models.CASCADE
    )
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
    # should be called Upload, but to do it we have to make the
    # constraints be manually named, which take a bit
    build_code = models.TextField(null=True)
    build_url = models.TextField(null=True)
    env = models.JSONField(null=True)
    flags = models.ManyToManyField(RepositoryFlag, through=UploadFlagMembership)
    job_code = models.TextField(null=True)
    name = models.CharField(null=True, max_length=100)
    provider = models.CharField(max_length=50, null=True)
    report = models.ForeignKey(
        "CommitReport", related_name="sessions", on_delete=models.CASCADE,
    )
    state = models.CharField(max_length=100)
    storage_path = models.TextField()
    order_number = models.IntegerField(null=True)
    upload_type = models.CharField(max_length=100, default="uploaded")
    upload_extras = models.JSONField(default=dict)
    state_id = models.IntegerField(null=True, choices=UploadState.choices())
    upload_type_id = models.IntegerField(null=True, choices=UploadType.choices())

    class Meta:
        db_table = "reports_upload"

    @property
    def download_url(self):
        repository = self.report.commit.repository
        return (
            reverse(
                "upload-download",
                kwargs={
                    "service": get_short_service_name(repository.author.service),
                    "owner_username": repository.author.username,
                    "repo_name": repository.name,
                },
            )
            + f"?path={self.storage_path}"
        )

    @property
    def ci_url(self):
        build_url = ci.get(self.provider, {}).get("build_url")
        if not build_url:
            return
        repository = self.report.commit.repository
        data = {
            "service_short": get_short_service_name(repository.author.service),
            "owner": repository.author,
            "upload": self,
            "repo": repository,
            "commit": self.report.commit,
        }
        return build_url.format(**data)

    @property
    def flag_names(self):
        return [flag.flag_name for flag in self.flags.all()]


class UploadLevelTotals(AbstractTotals):
    report_session = models.OneToOneField(
        ReportSession, db_column="upload_id", on_delete=models.CASCADE
    )

    class Meta:
        db_table = "reports_uploadleveltotals"
