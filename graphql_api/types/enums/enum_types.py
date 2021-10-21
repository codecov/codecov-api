from ariadne import EnumType

from graphql_api.types import enums

enum_types = [
    EnumType("RepositoryOrdering", enums.RepositoryOrdering),
    EnumType("OrderingDirection", enums.OrderingDirection),
    EnumType("CoverageLine", enums.CoverageLine),
    EnumType("ComparisonError", enums.ComparisonError),
    EnumType("TypeProjectOnboarding", enums.TypeProjectOnboarding),
    EnumType("GoalOnboarding", enums.GoalOnboarding),
    EnumType("PullRequestState", enums.PullRequestState),
]
