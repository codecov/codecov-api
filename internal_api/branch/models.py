from django.db import models
from django.contrib.postgres.fields import ArrayField

from internal_api.repo.models import Repository
from internal_api.commit.models import Commit
from codecov_auth.models import Owner


class Branch(models.Model):
    name = models.TextField(primary_key=True, db_column='branch')
    repository = models.ForeignKey(
        Repository, db_column='repoid', on_delete=models.CASCADE, related_name='branches')
    # author = models.ForeignKey(Owner, db_column='authors', on_delete=models.CASCADE,)
    authors = ArrayField(models.IntegerField(
        null=True, blank=True), null=True, blank=True, db_column='authors')
    head = models.ForeignKey(
        Commit, db_column='head', related_name='branch_head', on_delete=models.CASCADE,)
    updatestamp = models.DateTimeField(auto_now=True)
    # default = models.BooleanField()

    # @property
    # def authors(self):
    #     authors = []

    #     if self.author_ids is not None:
    #         if len(self.author_ids):
    #             for ownerid in self.author_ids:
    #                 owner = Owner.objects.get(ownerid=ownerid)
    #                 authors.append(owner)

    #     return authors

    class Meta:
        db_table = 'branches'
    pass
