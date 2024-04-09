from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

from codecov_auth.models import Owner


# Create your models here.
class YamlHistory(
    ExportModelOperationsMixin("legacy_migrations.yaml_history"), models.Model
):
    id = models.AutoField(primary_key=True)
    ownerid = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="ownerids", db_column="ownerid"
    )
    author = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="authors", db_column="author"
    )
    timestamp = models.DateTimeField()
    message = models.TextField(blank=True, null=True)
    source = models.TextField()
    diff = models.TextField(null=True)

    class Meta:
        db_table = "yaml_history"
        indexes = [models.Index(fields=["ownerid", "timestamp"])]
