from ariadne import EnumType

from graphql_api.types.enums import RepositoryOrdering, OrderingDirection, CoverageLine, ComparisonError, TypeProjectOnboarding, GoalOnboarding, PullRequestState

enum_types = [
    EnumType("RepositoryOrdering", RepositoryOrdering),
    EnumType("OrderingDirection", OrderingDirection),
    EnumType("CoverageLine", CoverageLine),
    EnumType("ComparisonError", ComparisonError),
    EnumType("TypeProjectOnboarding", TypeProjectOnboarding),
    EnumType("GoalOnboarding", GoalOnboarding),
    EnumType("PullRequestState", PullRequestState),
]
