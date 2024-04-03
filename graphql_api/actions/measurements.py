from datetime import datetime
from typing import Iterable, Mapping, Optional

from core.models import Repository
from timeseries.helpers import aggregate_measurements, aligned_start_date
from timeseries.models import Interval, MeasurementSummary


def measurements_by_ids(
    repository: Repository,
    measurable_name: str,
    measurable_ids: Iterable[str],
    interval: Interval,
    after: datetime,
    before: datetime,
    branch: Optional[str] = None,
) -> Mapping[int, Iterable[dict]]:
    queryset = MeasurementSummary.agg_by(interval).filter(
        name=measurable_name,
        owner_id=repository.author_id,
        repo_id=repository.pk,
        measurable_id__in=measurable_ids,
        timestamp_bin__gte=aligned_start_date(interval, after),
        timestamp_bin__lte=before,
    )

    if branch:
        queryset = queryset.filter(branch=branch)

    queryset = aggregate_measurements(
        queryset, ["timestamp_bin", "owner_id", "repo_id", "measurable_id"]
    )

    # group by measurable_id
    measurements = {}
    for measurement in queryset:
        measurable_id = measurement["measurable_id"]
        if measurable_id not in measurements:
            measurements[measurable_id] = []
        measurements[measurable_id].append(measurement)

    return measurements
