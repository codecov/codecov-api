from ariadne import EnumType

from .enums import (
    ComparisonError,
    CoverageLine,
    GoalOnboarding,
    OrderingDirection,
    PullRequestState,
    RepositoryOrdering,
    TypeProjectOnboarding,
)

enum_types = [
    EnumType("RepositoryOrdering", RepositoryOrdering),
    EnumType("OrderingDirection", OrderingDirection),
    EnumType("CoverageLine", CoverageLine),
    EnumType("ComparisonError", ComparisonError),
    EnumType("TypeProjectOnboarding", TypeProjectOnboarding),
    EnumType("GoalOnboarding", GoalOnboarding),
    EnumType("PullRequestState", PullRequestState),
]
