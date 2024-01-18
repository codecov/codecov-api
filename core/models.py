import random
import string
import uuid
from datetime import datetime
from typing import Optional

from django.contrib.postgres.fields import ArrayField, CITextField
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.functions import Lower, Substr, Upper
from django.forms import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property
from django_prometheus.models import ExportModelOperationsMixin
from model_utils import FieldTracker
from shared.config import get_config
from shared.reports.resources import Report

from codecov.models import BaseCodecovModel
from utils.config import should_write_data_to_storage_config_check
from utils.model_utils import ArchiveField

from .encoders import ReportJSONEncoder
from .managers import RepositoryManager


class DateTimeWithoutTZField(models.DateTimeField):
    def db_type(self, connection):
        return "timestamp"


class Version(ExportModelOperationsMixin("core.version"), models.Model):
    version = models.TextField(primary_key=True)

    class Meta:
        db_table = "version"


class Constants(ExportModelOperationsMixin("core.constants"), models.Model):
    key = models.CharField(primary_key=True)
    value = models.CharField()

    class Meta:
        db_table = "constants"


def _gen_image_token():
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(10)
    )


class Repository(ExportModelOperationsMixin("core.repository"), models.Model):
    class Languages(models.TextChoices):
        JAVASCRIPT = "javascript"
        SHELL = "shell"
        PYTHON = "python"
        RUBY = "ruby"
        PERL = "perl"
        DART = "dart"
        JAVA = "java"
        C = "c"
        CLOJURE = "clojure"
        D = "d"
        FORTRAN = "fortran"
        GO = "go"
        GROOVY = "groovy"
        KOTLIN = "kotlin"
        PHP = "php"
        R = "r"
        SCALA = "scala"
        SWIFT = "swift"
        OBJECTIVE_C = "objective-c"
        XTEND = "xtend"
        TYPESCRIPT = "typescript"
        HASKELL = "haskell"
        RUST = "rust"
        LUA = "lua"
        MATLAB = "matlab"
        ASSEMBLY = "assembly"
        SCHEME = "scheme"
        POWERSHELL = "powershell"
        APEX = "apex"
        VERILOG = "verilog"
        COMMON_LISP = "common lisp"
        ERLANG = "erlang"
        JULIA = "julia"
        PROLOG = "prolog"
        VUE = "vue"
        CPP = "c++"
        C_SHARP = "c#"
        F_SHARP = "f#"

    repoid = models.AutoField(primary_key=True)
    name = CITextField()
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="ownerid", on_delete=models.CASCADE
    )
    service_id = models.TextField()
    private = models.BooleanField()
    updatestamp = models.DateTimeField(auto_now=True)
    active = models.BooleanField(null=True, default=False)
    language = models.TextField(
        null=True, blank=True, choices=Languages.choices
    )  # Really an ENUM in db
    languages = ArrayField(models.CharField(), default=[], blank=True, null=True)
    languages_last_updated = DateTimeWithoutTZField(null=True, blank=True)
    fork = models.ForeignKey(
        "core.Repository",
        db_column="forkid",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    branch = models.TextField(default="master")
    upload_token = models.UUIDField(unique=True, default=uuid.uuid4)
    yaml = models.JSONField(null=True)
    image_token = models.TextField(null=True, default=_gen_image_token)

    # DEPRECATED - replaced by GithubAppInstallation model
    using_integration = models.BooleanField(null=True)

    hookid = models.TextField(null=True)
    webhook_secret = models.TextField(null=True)
    bot = models.ForeignKey(
        "codecov_auth.Owner",
        db_column="bot",
        null=True,
        on_delete=models.SET_NULL,
        related_name="bot_repos",
        blank=True,
    )
    activated = models.BooleanField(null=True, default=False)
    deleted = models.BooleanField(default=False)
    bundle_analysis_enabled = models.BooleanField(default=False, null=True)
    coverage_enabled = models.BooleanField(default=False, null=True)

    # tracks field changes being saved
    tracker = FieldTracker()

    class Meta:
        db_table = "repos"
        ordering = ["-repoid"]
        indexes = [
            models.Index(
                fields=["service_id", "author"],
                name="repos_service_id_author",
            ),
        ]
        constraints = [
            models.UniqueConstraint(fields=["author", "name"], name="repos_slug"),
            models.UniqueConstraint(
                fields=["author", "service_id"], name="repos_service_ids"
            ),
        ]
        verbose_name_plural = "Repositories"

    objects = RepositoryManager()

    def __str__(self):
        return f"Repo<{self.author}/{self.name}>"

    @property
    def service(self):
        return self.author.service

    def clean(self):
        if self.using_integration is None:
            raise ValidationError("using_integration cannot be null")


class Branch(ExportModelOperationsMixin("core.branch"), models.Model):
    name = models.TextField(primary_key=True, db_column="branch")
    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="branches",
    )
    authors = ArrayField(
        models.IntegerField(null=True, blank=True),
        null=True,
        blank=True,
        db_column="authors",
    )
    head = models.TextField()
    base = models.TextField(null=True)
    updatestamp = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branches"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "repository"], name="branches_repoid_branch"
            )
        ]
        indexes = [
            models.Index(
                fields=["repository", "-updatestamp"],
                name="branches_repoid_updatestamp",
            ),
        ]


class Commit(ExportModelOperationsMixin("core.commit"), models.Model):
    class CommitStates(models.TextChoices):
        COMPLETE = "complete"
        PENDING = "pending"
        ERROR = "error"
        SKIPPED = "skipped"

    id = models.BigAutoField(primary_key=True)
    commitid = models.TextField()
    timestamp = DateTimeWithoutTZField(default=timezone.now)
    updatestamp = DateTimeWithoutTZField(default=timezone.now)
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="author", on_delete=models.SET_NULL, null=True
    )
    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="commits",
    )
    ci_passed = models.BooleanField(null=True)
    totals = models.JSONField(null=True)
    merged = models.BooleanField(null=True)
    deleted = models.BooleanField(null=True)
    notified = models.BooleanField(null=True)
    branch = models.TextField(null=True)
    pullid = models.IntegerField(null=True)
    message = models.TextField(null=True)
    parent_commit_id = models.TextField(null=True, db_column="parent")
    state = models.TextField(
        null=True, choices=CommitStates.choices
    )  # Really an ENUM in db

    def save(self, *args, **kwargs):
        self.updatestamp = timezone.now()
        super().save(*args, **kwargs)

    @cached_property
    def parent_commit(self):
        return Commit.objects.filter(
            repository=self.repository, commitid=self.parent_commit_id
        ).first()

    @cached_property
    def commitreport(self):
        reports = list(self.reports.all())
        # This is almost always prefetched w/ `filter(code=None)` and
        # `filter(Q(report_type=None) | Q(report_type=CommitReport.ReportType.COVERAGE))`
        # (in which case `.all()` returns the already filtered results)
        # In the case that the reports were not prefetched we'll filter again in memory.
        reports = [
            report
            for report in reports
            if report.code is None
            and (report.report_type is None or report.report_type == "coverage")
        ]
        return reports[0] if reports else None

    @cached_property
    def full_report(self) -> Optional[Report]:
        # TODO: we should probably remove use of this method since it inverts the
        # dependency tree (services should be importing models and not the other
        # way around).  The caching should be preserved somehow though.
        from services.report import build_report_from_commit

        return build_report_from_commit(self)

    class Meta:
        db_table = "commits"
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "commitid"], name="commits_repoid_commitid"
            )
        ]
        indexes = [
            models.Index(
                fields=["repository", "-timestamp"],
                name="commits_repoid_timestamp_desc",
            ),
            models.Index(
                fields=["repository", "branch", "state", "-timestamp"],
                name="commits_repoid_branch_state_ts",
            ),
            models.Index(
                fields=["repository", "pullid"],
                name="commits_on_pull",
                condition=~models.Q(deleted=True),
            ),
            models.Index(
                fields=["repository", "pullid"],
                name="all_commits_on_pull",
            ),
            models.Index(
                "repository",
                Substr(Lower("commitid"), 1, 7),
                name="commits_repoid_commitid_short",
            ),
            GinIndex(
                "repository",
                OpClass(Upper("message"), name="gin_trgm_ops"),
                name="commit_message_gin_trgm",
            ),
        ]

    def get_repository(self):
        return self.repository

    def get_commitid(self):
        return self.commitid

    @property
    def external_id(self):
        return self.commitid

    def should_write_to_storage(self) -> bool:
        if self.repository is None or self.repository.author is None:
            return False
        is_codecov_repo = self.repository.author.username == "codecov"
        return should_write_data_to_storage_config_check(
            "commit_report", is_codecov_repo, self.repository.repoid
        )

    # Use custom JSON to properly serialize custom data classes on reports
    _report = models.JSONField(null=True, db_column="report", encoder=ReportJSONEncoder)
    _report_storage_path = models.URLField(null=True, db_column="report_storage_path")
    report = ArchiveField(
        should_write_to_storage_fn=should_write_to_storage,
        json_encoder=ReportJSONEncoder,
        default_value_class=dict,
    )


class PullStates(models.TextChoices):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class Pull(ExportModelOperationsMixin("core.pull"), models.Model):
    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="pull_requests",
    )
    id = models.BigAutoField(primary_key=True)
    pullid = models.IntegerField()
    issueid = models.IntegerField(null=True)
    state = models.TextField(
        choices=PullStates.choices, default=PullStates.OPEN.value
    )  # Really an ENUM in db
    title = models.TextField(null=True)
    base = models.TextField(null=True)
    head = models.TextField(null=True)
    user_provided_base_sha = models.TextField(null=True)
    compared_to = models.TextField(null=True)
    commentid = models.TextField(null=True)
    bundle_analysis_commentid = models.TextField(null=True)
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="author", on_delete=models.SET_NULL, null=True
    )
    updatestamp = DateTimeWithoutTZField(default=timezone.now)
    diff = models.JSONField(null=True)
    behind_by = models.IntegerField(null=True)
    behind_by_commit = models.TextField(null=True)

    class Meta:
        db_table = "pulls"
        ordering = ["-pullid"]
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "pullid"], name="pulls_repoid_pullid"
            )
        ]
        indexes = [
            models.Index(
                fields=["repository"],
                name="pulls_repoid_state_open",
                condition=models.Q(state=PullStates.OPEN.value),
            ),
            models.Index(
                fields=["author", "updatestamp"],
                name="pulls_author_updatestamp",
            ),
            models.Index(
                fields=["repository", "pullid", "updatestamp"],
                name="pulls_repoid_pullid_ts",
            ),
            models.Index(
                fields=["repository", "id"],
                name="pulls_repoid_id",
            ),
        ]

    def get_repository(self):
        return self.repository

    def get_commitid(self):
        return None

    @property
    def external_id(self):
        return self.pullid

    def should_write_to_storage(self) -> bool:
        if self.repository is None or self.repository.author is None:
            return False
        is_codecov_repo = self.repository.author.username == "codecov"
        return should_write_data_to_storage_config_check(
            master_switch_key="pull_flare",
            is_codecov_repo=is_codecov_repo,
            repoid=self.repository.repoid,
        )

    _flare = models.JSONField(db_column="flare", null=True)
    _flare_storage_path = models.URLField(db_column="flare_storage_path", null=True)
    flare = ArchiveField(
        should_write_to_storage_fn=should_write_to_storage, default_value_class=dict
    )

    def save(self, *args, **kwargs):
        self.updatestamp = timezone.now()
        super().save(*args, **kwargs)


class CommitNotification(
    ExportModelOperationsMixin("core.commit_notification"), models.Model
):
    class NotificationTypes(models.TextChoices):
        COMMENT = "comment"
        GITTER = "gitter"
        HIPCHAT = "hipchat"
        IRC = "irc"
        SLACK = "slack"
        STATUS_CHANGES = "status_changes"
        STATUS_PATCH = "status_patch"
        STATUS_PROJECT = "status_project"
        WEBHOOK = "webhook"
        CODECOV_SLACK_APP = "codecov_slack_app"

    class DecorationTypes(models.TextChoices):
        STANDARD = "standard"
        UPGRADE = "upgrade"
        UPLOAD_LIMIT = "upload_limit"
        PASSING_EMPTY_UPLOAD = "passing_empty_upload"
        FAILING_EMPTY_UPLOAD = "failing_empty_upload"
        PROCESSING_UPLOAD = "processing_upload"

    class States(models.TextChoices):
        PENDING = "pending"
        SUCCESS = "success"
        ERROR = "error"

    id = models.BigAutoField(primary_key=True)
    commit = models.ForeignKey(
        "core.Commit", on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.TextField(
        choices=NotificationTypes.choices
    )  # Really an ENUM in db
    decoration_type = models.TextField(
        choices=DecorationTypes.choices, null=True
    )  # Really an ENUM in db
    state = models.TextField(choices=States.choices, null=True)  # Really an ENUM in db
    created_at = DateTimeWithoutTZField(default=datetime.now)
    updated_at = DateTimeWithoutTZField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "commit_notifications"


class CommitError(ExportModelOperationsMixin("core.commit_error"), BaseCodecovModel):
    commit = models.ForeignKey(
        "Commit",
        related_name="errors",
        on_delete=models.CASCADE,
    )
    error_code = models.CharField(max_length=100)
    error_params = models.JSONField(default=dict)
