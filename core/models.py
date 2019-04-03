# from django.db import models
# from django.contrib.postgres.fields import JSONField, CITextField, ArrayField
# from django.utils.functional import cached_property
# from urllib.parse import urlparse


# class Branch(models.Model):
#     name = models.TextField(primary_key=True, db_column='branch')
#     repository = models.ForeignKey(
#         'Repository', db_column='repoid', on_delete=models.CASCADE, related_name='branches')
#     # author = models.ForeignKey('codecov_auth.Owner', db_column='authors', on_delete=models.CASCADE,)
#     authors = ArrayField(models.IntegerField(null=True, blank=True), null=True, blank=True)
#     head = models.CharField(max_length=256)
#     updatestamp = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'branches'
#     pass


# class Commit(models.Model):
#     commitid = models.TextField(primary_key=True)
#     timestamp = models.DateTimeField(auto_now_add=True)
#     updatestamp = models.DateTimeField(auto_now=True)
#     author = models.ForeignKey('codecov_auth.Owner', db_column='author', on_delete=models.CASCADE,)
#     ci_passed = models.BooleanField()
#     repository = models.ForeignKey(
#         'Repository', db_column='repoid', on_delete=models.CASCADE, related_name='commits')
#     totals = JSONField()
#     report = JSONField()
#     merged = models.NullBooleanField()
#     deleted = models.NullBooleanField()
#     notified = models.NullBooleanField()
#     branch = models.TextField()
#     pullid = models.IntegerField()
#     message = models.TextField()
#     parent_commit_id = models.TextField(db_column='parent')
#     state = models.CharField(max_length=256)

#     @cached_property
#     def parent_commit(self):
#         return Commit.objects.filter(repository=self.repository, commitid=self.parent_commit_id).first()

#     class Meta:
#         db_table = 'commits'
#     pass


# class Pull(models.Model):
#     repository = models.ForeignKey('Repository', db_column='repoid', on_delete=models.CASCADE, related_name='pull_requests')
#     pullid = models.IntegerField(primary_key=True)
#     issueid = models.IntegerField()
#     state = models.CharField(max_length=100)
#     title = models.CharField(max_length=100)
#     base = models.CharField(max_length=100)
#     compared_to = models.CharField(max_length=100)
#     head = models.CharField(max_length=100)
#     commentid = models.CharField(max_length=100)
#     diff = JSONField()
#     flare = JSONField()
#     author = models.ForeignKey('codecov_auth.Owner', db_column='author', on_delete=models.CASCADE,)
#     updatestamp = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'pulls'
#     pass


# class Repository(models.Model):
#     repoid = models.AutoField(primary_key=True)
#     name = CITextField()
#     author = models.ForeignKey('codecov_auth.Owner', db_column='ownerid', on_delete=models.CASCADE,)
#     service_id = models.TextField()
#     private = models.BooleanField()
#     updatestamp = models.DateTimeField(auto_now=True)
#     active = models.NullBooleanField()

#     class Meta:
#         db_table = 'repos'

#     @property
#     def service(self):
#         return self.owner.ownerid


# class YamlHistory(models.Model):

#     class Meta:
#         db_table = 'yaml_history'
#     pass
