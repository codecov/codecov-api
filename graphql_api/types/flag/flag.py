from typing import Iterable

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from reports.models import RepositoryFlag
from timeseries.models import Interval, MeasurementSummary

flag_bindable = ObjectType("Flag")


@flag_bindable.field("name")
def resolve_timestamp(flag: RepositoryFlag, info) -> str:
    return flag.flag_name


@flag_bindable.field("percentCovered")
@sync_to_async
def resolve_percent_covered(flag: RepositoryFlag, info) -> float:
    if "measurements" not in info.context:
        return None

    # measurements are fetched in parent resolver
    measurements = [
        measurement
        for measurement in info.context["measurements"]
        if measurement["flag_id"] == flag.pk
    ]

    if len(measurements) > 0:
        return measurements[-1]["avg"]


@flag_bindable.field("measurements")
@sync_to_async
def resolve_measurements(
    flag: RepositoryFlag, info, interval: Interval, after: str, before: str
) -> Iterable[MeasurementSummary]:
    # measurements are fetched in parent resolver
    return [
        measurement
        for measurement in info.context["measurements"]
        if measurement["flag_id"] == flag.pk
    ]
