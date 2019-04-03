from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.functional import cached_property
from internal_api.repo.models import Repository
from codecov_auth.models import Owner


class Commit(models.Model):
    commitid = models.TextField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    updatestamp = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(Owner, db_column='author', on_delete=models.CASCADE,)
    repository = models.ForeignKey(Repository, db_column='repoid', on_delete=models.CASCADE, related_name='commits')
    ci_passed = models.BooleanField()
    totals = JSONField()
    report = JSONField()
    merged = models.NullBooleanField()
    deleted = models.NullBooleanField()
    notified = models.NullBooleanField()
    branch = models.TextField()
    pullid = models.IntegerField()
    message = models.TextField()
    parent_commit_id = models.TextField(db_column='parent')
    state = models.CharField(max_length=256)

    @cached_property
    def parent_commit(self):
        return Commit.objects.filter(repository=self.repository, commitid=self.parent_commit_id).first()

    class Meta:
        db_table = 'commits'
    pass