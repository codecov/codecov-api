from django.db import models
from django.contrib.postgres.fields import JSONField, CITextField


class Branch(models.Model):

    class Meta:
        db_table = 'branches'
    pass


class Commit(models.Model):

    commitid = models.TextField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    updatestamp = models.DateTimeField(auto_now=True)
    author = models.ForeignKey('codecov_auth.Owner', db_column='author', on_delete=models.CASCADE,)
    ci_passed = models.BooleanField()
    repository = models.ForeignKey('Repository', db_column='repoid', on_delete=models.CASCADE, related_name='commits')
    totals = JSONField()
    report = JSONField()

    @property
    def minio_report_path(self):
        return self.sessions[-1]['a']

    @property
    def sessions(self):
        sessions = sorted(self.report['sessions'].items(), key=lambda a: int(a[0]))
        return [s[1] for s in sessions]

  # timestamp               timestamp not null,
  # branch                  text,
  # pullid                  int,
  # message                 text,
  # state                   commit_state,
  # merged                  boolean,
  # deleted                 boolean,
  # notified                boolean,
  # version                 smallint,  -- will be removed after migrations
  # parent                  text,

    class Meta:
        db_table = 'commits'
    pass


class Pull(models.Model):

    repository = models.ForeignKey('Repository', db_column='repoid', on_delete=models.CASCADE, related_name='pull_requests')
    pullid = models.IntegerField(primary_key=True)
    issueid = models.IntegerField()
    updatestamp = models.DateTimeField(auto_now=True)
    state = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    base = models.CharField(max_length=100)
    compared_to = models.CharField(max_length=100)
    head = models.CharField(max_length=100)
    commentid = models.CharField(max_length=100)
    diff = JSONField()
    flare = JSONField()
    author = models.ForeignKey('codecov_auth.Owner', db_column='author', on_delete=models.CASCADE,)

    class Meta:
        db_table = 'pulls'
    pass


class Repository(models.Model):

    repoid = models.IntegerField(primary_key=True)
    owner = models.ForeignKey('codecov_auth.Owner', db_column='ownerid', on_delete=models.CASCADE,)
    service_id = models.TextField()
    name = CITextField()
    private = models.BooleanField()
    updatestamp = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'repos'


class YamlHistory(models.Model):

    class Meta:
        db_table = 'yaml_history'
    pass
