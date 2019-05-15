from django.db import models
from django.contrib.postgres.fields import JSONField
from internal_api.repo.models import Repository
from internal_api.commit.models import Commit
from codecov_auth.models import Owner


class Pull(models.Model):
    repository = models.ForeignKey(
        Repository, db_column='repoid', on_delete=models.CASCADE, related_name='pull_requests')
    pullid = models.IntegerField(primary_key=True)
    issueid = models.IntegerField()
    state = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    base = models.ForeignKey(Commit, db_column='base',
                             related_name='pull_base', on_delete=models.CASCADE,)
    head = models.ForeignKey(Commit, db_column='head',
                             related_name='pull_head', on_delete=models.CASCADE,)
    compared_to = models.ForeignKey(
        Commit, db_column='compared_to', related_name='compared_to', on_delete=models.CASCADE,)
    commentid = models.CharField(max_length=100)
    author = models.ForeignKey(
        Owner, db_column='author', on_delete=models.CASCADE,)
    updatestamp = models.DateTimeField(auto_now=True)
    diff = JSONField()
    flare = JSONField()

    class Meta:
        db_table = 'pulls'
