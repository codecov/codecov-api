from datetime import datetime
from typing import Iterable

from ariadne import ObjectType

from reports.models import RepositoryFlag
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval, MeasurementSummary

flag_bindable = ObjectType("Flag")

# NOTE: measurements are fetched in the parent resolver (repository) and
# placed in the context so that they can be used in multiple resolvers here


@flag_bindable.field("name")
def resolve_timestamp(flag: RepositoryFlag, info) -> str:
    return flag.flag_name


@flag_bindable.field("percentCovered")
def resolve_percent_covered(flag: RepositoryFlag, info) -> float:
    if "flag_measurements" not in info.context:
        # we rely on measurements for this computed value
        return None

    measurements = info.context["flag_measurements"].get(flag.pk, [])
    if len(measurements) > 0:
        # coverage returned is the most recent measurement average
        return measurements[-1]["avg"]


@flag_bindable.field("percentChange")
def resolve_percent_change(flag: RepositoryFlag, info) -> float:
    if "flag_measurements" not in info.context:
        # we rely on measurements for this computed value
        return None

    measurements = info.context["flag_measurements"].get(flag.pk, [])
    if len(measurements) > 1:
        return measurements[-1]["avg"] - measurements[0]["avg"]


@flag_bindable.field("measurements")
def resolve_measurements(
    flag: RepositoryFlag, info, interval: Interval, after: datetime, before: datetime
) -> Iterable[MeasurementSummary]:
    measurements = info.context["flag_measurements"].get(flag.pk, [])
    if len(measurements) == 0:
        return []
    return fill_sparse_measurements(measurements, interval, after, before)
