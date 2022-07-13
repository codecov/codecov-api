from ariadne import EnumType

from timeseries.models import Interval as MeasurementInterval

from .enums import (
    ComparisonError,
    CoverageLine,
    GoalOnboarding,
    OrderingDirection,
    OrderingParameter,
    PullRequestState,
    RepositoryOrdering,
    TypeProjectOnboarding,
    UploadErrorEnum,
    UploadState,
    UploadType,
)

enum_types = [
    EnumType("RepositoryOrdering", RepositoryOrdering),
    EnumType("OrderingDirection", OrderingDirection),
    EnumType("CoverageLine", CoverageLine),
    EnumType("ComparisonError", ComparisonError),
    EnumType("TypeProjectOnboarding", TypeProjectOnboarding),
    EnumType("GoalOnboarding", GoalOnboarding),
    EnumType("OrderingParameter", OrderingParameter),
    EnumType("PullRequestState", PullRequestState),
    EnumType("UploadState", UploadState),
    EnumType("UploadType", UploadType),
    EnumType("UploadErrorEnum", UploadErrorEnum),
    EnumType("MeasurementInterval", MeasurementInterval),
]
