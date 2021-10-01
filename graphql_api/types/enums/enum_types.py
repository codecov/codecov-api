from ariadne import EnumType

from . import enums

enum_types = [
    EnumType("RepositoryOrdering", enums.RepositoryOrdering),
    EnumType("OrderingDirection", enums.OrderingDirection),
    EnumType("CoverageLine", enums.CoverageLine),
    EnumType("ComparisonError", enums.ComparisonError),
    EnumType("TypeProjectOnboarding", enums.TypeProjectOnboarding),
    EnumType("GoalOnboarding", enums.GoalOnboarding),
]
