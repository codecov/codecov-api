from ariadne import EnumType

from .enums import RepositoryOrdering, OrderingDirection, CoverageLine

repository_ordering = EnumType("RepositoryOrdering", RepositoryOrdering)
ordering_direction = EnumType("OrderingDirection", OrderingDirection)
coverage_line = EnumType("CoverageLine", CoverageLine)

enum_types = [
    repository_ordering,
    ordering_direction,
    coverage_line,
]
