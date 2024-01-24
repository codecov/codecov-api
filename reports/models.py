import logging
import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from django_prometheus.models import ExportModelOperationsMixin
from shared.config import get_config
from shared.reports.enums import UploadState, UploadType

from codecov.models import BaseCodecovModel
from reports.managers import CommitReportManager
from upload.constants import ci
from utils.config import should_write_data_to_storage_config_check
from utils.model_utils import ArchiveField
from utils.services import get_short_service_name

log = logging.getLogger(__name__)


class AbstractTotals(
    ExportModelOperationsMixin("reports.abstract_totals"), BaseCodecovModel
):
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


class CommitReport(
    ExportModelOperationsMixin("reports.commit_report"), BaseCodecovModel
):
    class ReportType(models.TextChoices):
        COVERAGE = "coverage"
        TEST_RESULTS = "test_results"
        BUNDLE_ANALYSIS = "bundle_analysis"

    commit = models.ForeignKey(
        "core.Commit", related_name="reports", on_delete=models.CASCADE
    )
    code = models.CharField(null=True, max_length=100)
    report_type = models.CharField(
        null=True, max_length=100, choices=ReportType.choices
    )

    objects = CommitReportManager()


class ReportResults(
    ExportModelOperationsMixin("reports.report_results"), BaseCodecovModel
):
    class ReportResultsStates(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"
        ERROR = "error"

    report = models.OneToOneField(CommitReport, on_delete=models.CASCADE)
    state = models.TextField(null=True, choices=ReportResultsStates.choices)
    completed_at = models.DateTimeField(null=True)
    result = models.JSONField(default=dict)


class ReportDetails(
    ExportModelOperationsMixin("reports.report_details"), BaseCodecovModel
):
    report = models.OneToOneField(CommitReport, on_delete=models.CASCADE)
    _files_array = ArrayField(models.JSONField(), db_column="files_array", null=True)
    _files_array_storage_path = models.URLField(
        db_column="files_array_storage_path", null=True
    )

    def get_repository(self):
        return self.report.commit.repository

    def get_commitid(self):
        return self.report.commit.commitid

    def should_write_to_storage(self) -> bool:
        if (
            self.report is None
            or self.report.commit is None
            or self.report.commit.repository is None
            or self.report.commit.repository.author is None
        ):
            return False
        is_codecov_repo = self.report.commit.repository.author.username == "codecov"
        return should_write_data_to_storage_config_check(
            master_switch_key="report_details_files_array",
            is_codecov_repo=is_codecov_repo,
            repoid=self.report.commit.repository.repoid,
        )

    files_array = ArchiveField(
        should_write_to_storage_fn=should_write_to_storage,
        default_value_class=list,
    )


class ReportLevelTotals(AbstractTotals):
    report = models.OneToOneField(CommitReport, on_delete=models.CASCADE)


class UploadError(ExportModelOperationsMixin("reports.upload_error"), BaseCodecovModel):
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


class UploadFlagMembership(
    ExportModelOperationsMixin("reports.upload_flag_membership"), models.Model
):
    report_session = models.ForeignKey(
        "ReportSession", db_column="upload_id", on_delete=models.CASCADE
    )
    flag = models.ForeignKey("RepositoryFlag", on_delete=models.CASCADE)
    id = models.BigAutoField(primary_key=True)

    class Meta:
        db_table = "reports_uploadflagmembership"


class RepositoryFlag(
    ExportModelOperationsMixin("reports.repository_flag"), BaseCodecovModel
):
    repository = models.ForeignKey(
        "core.Repository", related_name="flags", on_delete=models.CASCADE
    )
    flag_name = models.CharField(max_length=1024)
    deleted = models.BooleanField(null=True)


class ReportSession(
    ExportModelOperationsMixin("reports.report_session"), BaseCodecovModel
):
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
        "CommitReport", related_name="sessions", on_delete=models.CASCADE
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
        if self.build_url:
            # build_url was saved in the database
            return self.build_url

        # otherwise we need to construct it ourself (if possible)
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


class Test(models.Model):
    # the reason we aren't using the regular primary key
    # in this case is because we want to be able to compute/predict
    # the primary key of a Test object ourselves in the processor
    # so we can easily do concurrent writes to the database
    id = models.TextField(primary_key=True)

    external_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        related_name="tests",
        on_delete=models.CASCADE,
    )
    name = models.TextField()
    testsuite = models.TextField()
    env = models.TextField()

    class Meta:
        db_table = "reports_test"


class TestInstance(BaseCodecovModel):
    test = models.ForeignKey(
        "Test",
        db_column="test_id",
        related_name="testinstances",
        on_delete=models.CASCADE,
    )
    duration_seconds = models.FloatField()
    outcome = models.IntegerField()
    upload = models.ForeignKey(
        "ReportSession",
        db_column="upload_id",
        related_name="testinstances",
        on_delete=models.CASCADE,
    )
    failure_message = models.TextField(null=True)

    class Meta:
        db_table = "reports_testinstance"
