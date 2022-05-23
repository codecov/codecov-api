import django.db.models as models


class Measurement(models.Model):
    # TimescaleDB requires that `timestamp` be part of every index (since data is
    # partitioned by `timestamp`).  Since an auto-incrementing primary key would
    # not satisfy this requirement we can make `timestamp` the primary key.`
    # Timesamp may not be unique though so we drop the uniqueness constraint in
    # a migration.
    timestamp = models.DateTimeField(null=False, primary_key=True)

    owner_id = models.BigIntegerField(null=False)
    repo_id = models.BigIntegerField(null=False)
    branch = models.TextField(null=True)
    name = models.TextField(null=False, blank=False)
    meta = models.TextField(null=True)
    value = models.FloatField(null=False)

    class Meta:
        indexes = [
            models.Index(
                fields=["owner_id", "repo_id", "branch", "name", "meta", "timestamp"]
            ),
        ]
