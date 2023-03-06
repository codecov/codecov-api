from ariadne import EnumType

from compare.commands.compare.interactors.fetch_impacted_files import (
    ImpactedFileParameter,
)
from timeseries.models import Interval as MeasurementInterval

from .enums import (
    CoverageLine,
    GoalOnboarding,
    LoginProvider,
    OrderingDirection,
    OrderingParameter,
    PathContentDisplayType,
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
    EnumType("PathContentDisplayType", PathContentDisplayType),
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
