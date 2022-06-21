from datetime import datetime

from ariadne import ObjectType

from timeseries.models import MeasurementSummary

measurement_bindable = ObjectType("Measurement")


@measurement_bindable.field("timestamp")
def resolve_timestamp(measurement: MeasurementSummary, info) -> datetime:
    return measurement.timestamp_bin


@measurement_bindable.field("avg")
def resolve_avg(measurement: MeasurementSummary, info) -> float:
    return measurement.value_avg


@measurement_bindable.field("min")
def resolve_min(measurement: MeasurementSummary, info) -> float:
    return measurement.value_min


@measurement_bindable.field("max")
def resolve_max(measurement: MeasurementSummary, info) -> float:
    return measurement.value_max
