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


class MeasurementSummary(models.Model):
    timestamp_bin = models.DateTimeField(primary_key=True)
    owner_id = models.BigIntegerField()
    repo_id = models.BigIntegerField()
    branch = models.TextField()
    name = models.TextField()
    meta = models.TextField()
    value_avg = models.FloatField()
    value_max = models.FloatField()
    value_min = models.FloatField()
    value_count = models.FloatField()

    @classmethod
    def agg_by(cls, interval):
        model_classes = {
            "hour": MeasurementSummaryHour,
            "day": MeasurementSummaryDay,
            "week": MeasurementSummaryWeek,
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


class MeasurementSummaryHour(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_hour"


class MeasurementSummaryDay(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_day"


class MeasurementSummaryWeek(MeasurementSummary):
    class Meta(MeasurementSummary.Meta):
        db_table = "timeseries_measurement_summary_week"
