from django.db import models
from django.contrib.postgres.fields import CITextField


class Repository(models.Model):
    repoid = models.AutoField(primary_key=True)
    name = CITextField()
    author = models.ForeignKey(
        'codecov_auth.Owner', db_column='ownerid', on_delete=models.CASCADE,)
    service_id = models.TextField()
    private = models.BooleanField()
    updatestamp = models.DateTimeField(auto_now=True)
    active = models.NullBooleanField()

    class Meta:
        db_table = 'repos'

    @property
    def service(self):
        return self.author.ownerid
