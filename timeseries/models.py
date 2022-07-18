from enum import Enum

import django.db.models as models
from django.db import connections


class Interval(Enum):
    INTERVAL_1_DAY = 1
    INTERVAL_7_DAY = 7
    INTERVAL_30_DAY = 30


class MeasurementName(Enum):
    COVERAGE = "coverage"
    FLAG_COVERAGE = "flag_coverage"


class Measurement(models.Model):
    # TimescaleDB requires that `timestamp` be part of every index (since data is
    # partitioned by `timestamp`).  Since an auto-incrementing primary key would
    # not satisfy this requirement we can make `timestamp` the primary key.
    # `timestamp` may not be unique though so we drop the uniqueness constraint in
    # a migration.
    timestamp = models.DateTimeField(null=False, primary_key=True)

    owner_id = models.BigIntegerField(null=False)
    repo_id = models.BigIntegerField(null=False)
    flag_id = models.BigIntegerField(null=True)
    branch = models.TextField(null=True)

    # useful for updating a measurement if needed
    commit_sha = models.TextField(null=True)

    # the name of the measurement (i.e. "coverage")
    name = models.TextField(null=False, blank=False)
    value = models.FloatField(null=False)

    class Meta:
        indexes = [
            # for querying measurements
            models.Index(
                fields=[
                    "owner_id",
                    "repo_id",
                    "flag_id",
                    "branch",
                    "name",
                    "timestamp",
                ]
            ),
        ]
        constraints = [
            # for updating measurements
            models.UniqueConstraint(
                fields=[
                    "name",
                    "owner_id",
                    "repo_id",
                    "flag_id",
                    "commit_sha",
                    "timestamp",
                ],
                condition=models.Q(flag_id__isnull=False),
                name="timeseries_measurement_flag_unique",
            ),
            models.UniqueConstraint(
                fields=[
                    "name",
                    "owner_id",
                    "repo_id",
                    "commit_sha",
                    "timestamp",
                ],
                condition=models.Q(flag_id__isnull=True),
                name="timeseries_measurement_noflag_unique",
            ),
        ]

    def upsert(self):
        """
        Insert or update a measurement
        """
        conflict_target = (
            "(name, owner_id, repo_id, commit_sha, timestamp) WHERE flag_id IS NULL"
            if self.flag_id is None
            else "(name, owner_id, repo_id, flag_id, commit_sha, timestamp) WHERE flag_id IS NOT NULL"
        )

        sql = f"""
            INSERT INTO timeseries_measurement
                (name, owner_id, repo_id, flag_id, branch, commit_sha, timestamp, value)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT {conflict_target}
            DO UPDATE SET
                branch = EXCLUDED.branch,
                value = EXCLUDED.value
        """

        connection = connections["timeseries"]
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                [
                    self.name,
                    self.owner_id,
                    self.repo_id,
                    self.flag_id,
                    self.branch,
                    self.commit_sha,
                    self.timestamp,
                    self.value,
                ],
            )


class MeasurementSummary(models.Model):
    timestamp_bin = models.DateTimeField(primary_key=True)
    owner_id = models.BigIntegerField()
    repo_id = models.BigIntegerField()
    flag_id = models.BigIntegerField()
    branch = models.TextField()
    name = models.TextField()
    value_avg = models.FloatField()
    value_max = models.FloatField()
    value_min = models.FloatField()
    value_count = models.FloatField()

    @classmethod
    def agg_by(cls, interval: Interval) -> models.Manager:
        model_classes = {
            Interval.INTERVAL_1_DAY: MeasurementSummary1Day,
            Interval.INTERVAL_7_DAY: MeasurementSummary7Day,
            Interval.INTERVAL_30_DAY: MeasurementSummary30Day,
        }

        model_class = model_classes.get(interval)
        if not model_class:
            raise ValueError(f"cannot aggregate by '{interval}'")
        return model_class.objects

    class Meta:
        abstract = True
        # these are backed by TimescaleDB "continuous aggregates"
        # (materialized views)
        managed = False
        ordering = ["timestamp_bin"]


class MeasurementSummary1Day(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_1day"


# Timescale's origin for time buckets is Monday 2000-01-03
# Weekly aggregate bins will thus be Monday-Sunday
class MeasurementSummary7Day(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_7day"


# Timescale's origin for time buckets is 2000-01-03
# 30 day offsets will be aligned on that origin
class MeasurementSummary30Day(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_30day"


class Dataset(models.Model):
    # this will likely correspond to a measurement name above
    name = models.TextField(null=False, blank=False)

    # not a true foreign key since repositories are in a
    # different database
    repository_id = models.IntegerField(null=False)

    # indicates whether the backfill task has completed for this dataset
    backfilled = models.BooleanField(null=False, default=False)

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "name",
                    "repository_id",
                ]
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "name",
                    "repository_id",
                ],
                name="name_repository_id_unique",
            ),
        ]
