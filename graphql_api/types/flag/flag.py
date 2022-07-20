from typing import Iterable

from ariadne import ObjectType

from graphql_api.actions.flags import fill_empty_measurements
from reports.models import RepositoryFlag
from timeseries.models import Interval, MeasurementSummary

flag_bindable = ObjectType("Flag")

# NOTE: measurements are fetched in the parent resolver (repository) and
# placed in the context so that they can be used in multiple resolvers here


@flag_bindable.field("name")
def resolve_timestamp(flag: RepositoryFlag, info) -> str:
    return flag.flag_name


@flag_bindable.field("percentCovered")
def resolve_percent_covered(flag: RepositoryFlag, info) -> float:
    if "measurements" not in info.context:
        # we rely on measurements for this computed value
        return None

    measurements = info.context["measurements"].get(flag.pk, [])
    if len(measurements) > 0:
        # coverage returned is the most recent measurement average
        return measurements[-1]["avg"]


@flag_bindable.field("percentChange")
def resolve_percent_change(flag: RepositoryFlag, info) -> float:
    if "measurements" not in info.context:
        # we rely on measurements for this computed value
        return None

    measurements = info.context["measurements"].get(flag.pk, [])
    if len(measurements) > 0:
        return ((measurements[-1]["avg"] / measurements[0]["avg"]) - 1) * 100


@flag_bindable.field("measurements")
def resolve_measurements(
    flag: RepositoryFlag, info, interval: Interval, after: str, before: str
) -> Iterable[MeasurementSummary]:
    measurements = info.context["measurements"].get(flag.pk, [])
    if len(measurements) == 0:
        return []
    return fill_empty_measurements(measurements, interval, after, before)
