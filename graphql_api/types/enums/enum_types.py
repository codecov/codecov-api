from ariadne import EnumType

from services.comparison import ImpactedFileParameter
from timeseries.models import Interval as MeasurementInterval

from .enums import (
    CoverageLine,
    GoalOnboarding,
    LoginProvider,
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
    EnumType("TypeProjectOnboarding", TypeProjectOnboarding),
    EnumType("GoalOnboarding", GoalOnboarding),
    EnumType("OrderingParameter", OrderingParameter),
    EnumType("PullRequestState", PullRequestState),
    EnumType("UploadState", UploadState),
    EnumType("UploadType", UploadType),
    EnumType("UploadErrorEnum", UploadErrorEnum),
    EnumType("MeasurementInterval", MeasurementInterval),
    EnumType("LoginProvider", LoginProvider),
    EnumType("ImpactedFileParameter", ImpactedFileParameter),
]
