import uuid
import string
import random

from django.db import models
from django.contrib.postgres.fields import CITextField, ArrayField
from django.utils.functional import cached_property

from .encoders import ReportJSONEncoder
from .managers import RepositoryQuerySet


class Version(models.Model):
    version = models.TextField(primary_key=True)

    class Meta:
        db_table = "version"


def _gen_image_token():
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(10)
    )


class Repository(models.Model):
    repoid = models.AutoField(primary_key=True)
    name = CITextField()
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="ownerid", on_delete=models.CASCADE,
    )
    service_id = models.TextField()
    private = models.BooleanField()
    updatestamp = models.DateTimeField(auto_now=True)
    active = models.BooleanField(null=True)
    language = models.TextField(null=True, blank=True)
    fork = models.ForeignKey(
        "core.Repository",
        db_column="forkid",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    branch = models.TextField(null=True, default="master")
    upload_token = models.UUIDField(default=uuid.uuid4)
    yaml = models.JSONField(null=True)
    cache = models.JSONField(null=True)
    image_token = models.CharField(max_length=10, default=_gen_image_token)
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

    objects = RepositoryQuerySet.as_manager()

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


class Commit(models.Model):
    class CommitStates:
        COMPLETE = "complete"
        PENDING = "pending"
        ERROR = "error"
        SKIPPED = "skipped"

    commitid = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    updatestamp = models.DateTimeField(auto_now=True)
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
    state = models.CharField(max_length=256)

    @cached_property
    def parent_commit(self):
        return Commit.objects.filter(
            repository=self.repository, commitid=self.parent_commit_id
        ).first()

    class Meta:
        db_table = "commits"


class Pull(models.Model):
    class PullStates:
        OPEN = "open"
        MERGED = "merged"
        CLOSED = "closed"

    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="pull_requests",
    )
    pullid = models.IntegerField(primary_key=True)
    issueid = models.IntegerField(null=True)
    state = models.CharField(max_length=100, default="open")
    title = models.CharField(max_length=100, null=True)
    base = models.TextField(null=True)
    head = models.TextField(null=True)
    compared_to = models.TextField(null=True)
    commentid = models.CharField(max_length=100, null=True)
    author = models.ForeignKey(
        "codecov_auth.Owner", db_column="author", on_delete=models.SET_NULL, null=True
    )
    updatestamp = models.DateTimeField(auto_now_add=True)
    diff = models.JSONField(null=True)
    flare = models.JSONField(null=True)

    class Meta:
        db_table = "pulls"
        ordering = ["-pullid"]
