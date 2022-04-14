from django.db import models

from codecov_auth.models import Owner


# Create your models here.
class YamlHistory(models.Model):
    ownerid = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="owner_id"
    )
    author = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="author")
    timestamp = models.DateTimeField()
    message = models.TextField(blank=True, null=True)
    source = models.TextField()
    diff = models.TextField(null=True)

    class Meta:
        db_table = "yaml_history"
        indexes = [models.Index(fields=["ownerid", "timestamp"])]
