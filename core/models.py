import random
import string
import uuid
from datetime import datetime

from django.contrib.postgres.fields import ArrayField, CITextField
from django.db import models
from django.utils.functional import cached_property

from services.archive import ReportService

from .encoders import ReportJSONEncoder
from .managers import RepositoryQuerySet


class DateTimeWithoutTZField(models.DateTimeField):
    def db_type(self, connection):
        return "timestamp"


class Version(models.Model):
    version = models.TextField(primary_key=True)

    class Meta:
        db_table = "version"


def _gen_image_token():
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(10)
    )


class Repository(models.Model):
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

    repoid = models.AutoField(primary_key=True)
    name = CITextField()
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="ownerid", on_delete=models.CASCADE,
    )
    service_id = models.TextField()
    private = models.BooleanField()
    updatestamp = models.DateTimeField(auto_now=True)
    active = models.BooleanField(null=True, default=False)
    language = models.TextField(
        null=True, blank=True, choices=Languages.choices
    )  # Really an ENUM in db
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
    cache = models.JSONField(null=True)
    image_token = models.TextField(null=True, default=_gen_image_token)
    using_integration = models.BooleanField(null=True)
    hookid = models.TextField(null=True)
    bot = models.ForeignKey(
        "codecov_auth.Owner",
        db_column="bot",
        null=True,
        on_delete=models.SET_NULL,
        related_name="bot_repos",
    )
    activated = models.BooleanField(null=True, default=False)
    deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "repos"
        ordering = ["-repoid"]
        constraints = [
            models.UniqueConstraint(fields=["author", "name"], name="repos_slug"),
            models.UniqueConstraint(
                fields=["author", "service_id"], name="repos_service_ids"
            ),
        ]
        verbose_name_plural = "Repositories"

    objects = RepositoryQuerySet.as_manager()

    def __str__(self):
        return f"Repo<{self.author}/{self.name}>"

    @property
    def service(self):
        return self.author.service

    def flush(self):
        self.commits.all().delete()
        self.branches.all().delete()
        self.pull_requests.all().delete()
        self.yaml = None
        self.cache = None
        self.save()


class Branch(models.Model):
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


class Commit(models.Model):
    class CommitStates(models.TextChoices):
        COMPLETE = "complete"
        PENDING = "pending"
        ERROR = "error"
        SKIPPED = "skipped"

    id = models.BigAutoField(primary_key=True)
    commitid = models.TextField()
    timestamp = DateTimeWithoutTZField(default=datetime.now)
    updatestamp = DateTimeWithoutTZField(default=datetime.now)
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
    # Use custom JSON to properly serialize custom data classes on reports
    report = models.JSONField(null=True, encoder=ReportJSONEncoder)
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
        self.updatestamp = datetime.now()
        super().save(*args, **kwargs)

    @cached_property
    def parent_commit(self):
        return Commit.objects.filter(
            repository=self.repository, commitid=self.parent_commit_id
        ).first()

    @classmethod
    def report_totals_by_file_name(cls, commit_id):
        """
        Commit.report can contain very large JSON blobs. Most of this data is report data per file per run, whereas
        for certain calculations only the totals over the entire runs are needed. This query should be used when that
        is the case for performance reasons.
        """
        return Commit.objects.raw(
            "SELECT id, json_data.key as file_name, json_data.value->1 as totals FROM commits, jsonb_each(commits.report->'files') as json_data WHERE commits.id = %s;",
            [commit_id],
        )

    @cached_property
    def commitreport(self):
        reports = list(self.reports.all())
        return reports[0] if reports else None

    @cached_property
    def full_report(self):
        report_service = ReportService()
        return report_service.build_report_from_commit(self)

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
                fields=["repository", "pullid"],
                name="commits_on_pull",
                condition=~models.Q(deleted=True),
            ),
        ]


class PullStates(models.TextChoices):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class Pull(models.Model):
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
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="author", on_delete=models.SET_NULL, null=True
    )
    updatestamp = DateTimeWithoutTZField(default=datetime.now)
    diff = models.JSONField(null=True)
    flare = models.JSONField(null=True)

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
            )
        ]

    def save(self, *args, **kwargs):
        self.updatestamp = datetime.now()
        super().save(*args, **kwargs)


class CommitNotification(models.Model):
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

    class DecorationTypes(models.TextChoices):
        STANDARD = "standard"
        UPGRADE = "upgrade"

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
        self.updated_at = datetime.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "commit_notifications"
