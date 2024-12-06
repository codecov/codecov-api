from ariadne import EnumType
from shared.plan.constants import TierName, TrialStatus

from codecov_auth.models import RepositoryToken
from compare.commands.compare.interactors.fetch_impacted_files import (
    ImpactedFileParameter,
)
from core.models import Commit
from services.yaml import YamlStates
from timeseries.models import Interval as MeasurementInterval
from timeseries.models import MeasurementName

from .enums import (
    AssetOrdering,
    BundleLoadTypes,
    CoverageLine,
    GoalOnboarding,
    LoginProvider,
    OrderingDirection,
    OrderingParameter,
    PathContentDisplayType,
    PullRequestState,
    RepositoryOrdering,
    SyncProvider,
    TestResultsFilterParameter,
    TestResultsOrderingParameter,
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
    EnumType("CommitState", Commit.CommitStates),
    EnumType("MeasurementType", MeasurementName),
    EnumType("RepositoryTokenType", RepositoryToken.TokenType),
    EnumType("SyncProvider", SyncProvider),
    EnumType("TierName", TierName),
    EnumType("TrialStatus", TrialStatus),
    EnumType("YamlStates", YamlStates),
    EnumType("BundleLoadTypes", BundleLoadTypes),
    EnumType("TestResultsOrderingParameter", TestResultsOrderingParameter),
    EnumType("TestResultsFilterParameter", TestResultsFilterParameter),
    EnumType("AssetOrdering", AssetOrdering),
]
