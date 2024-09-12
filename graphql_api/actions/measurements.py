from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from django.db.models import Max, QuerySet

from core.models import Repository
from timeseries.helpers import aggregate_measurements, aligned_start_date
from timeseries.models import Interval, Measurement, MeasurementSummary


def measurements_by_ids(
    repository: Repository,
    measurable_name: str,
    measurable_ids: Iterable[str],
    interval: Interval,
    before: datetime,
    after: Optional[datetime] = None,
    branch: Optional[str] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    queryset = MeasurementSummary.agg_by(interval).filter(
        name=measurable_name,
        owner_id=repository.author_id,
        repo_id=repository.pk,
        measurable_id__in=measurable_ids,
        timestamp_bin__lte=before,
    )

    if after is not None:
        queryset = queryset.filter(
            timestamp_bin__gte=aligned_start_date(interval, after)
        )

    if branch:
        queryset = queryset.filter(branch=branch)

    queryset = aggregate_measurements(
        queryset, ["timestamp_bin", "owner_id", "repo_id", "measurable_id"]
    )

    # group by measurable_id
    measurements: Dict[int, List[Dict[str, Any]]] = {}
    for measurement in queryset:
        measurable_id = measurement["measurable_id"]
        if measurable_id not in measurements:
            measurements[measurable_id] = []
        measurements[measurable_id].append(measurement)

    return measurements


def measurements_last_uploaded_before_start_date(
    owner_id: int,
    repo_id: int,
    measurable_name: str,
    measurable_id: int,
    start_date: datetime,
    branch: Optional[str] = None,
) -> QuerySet:
    queryset = Measurement.objects.filter(
        owner_id=owner_id,
        repo_id=repo_id,
        measurable_id=measurable_id,
        name=measurable_name,
        timestamp__lt=start_date,
    )

    if branch:
        queryset = queryset.filter(branch=branch)

    return queryset.values("measurable_id", "value").annotate(
        last_uploaded=Max("timestamp")
    )


def measurements_last_uploaded_by_ids(
    owner_id: int,
    repo_id: int,
    measurable_name: str,
    measurable_ids: str,
    branch: Optional[str] = None,
) -> QuerySet:
    queryset = Measurement.objects.filter(
        owner_id=owner_id,
        repo_id=repo_id,
        measurable_id__in=measurable_ids,
        name=measurable_name,
    )

    if branch:
        queryset = queryset.filter(branch=branch)

    return queryset.values("measurable_id").annotate(last_uploaded=Max("timestamp"))
