from ariadne import EnumType

from .enums import RepositoryOrdering, OrderingDirection

repository_ordering = EnumType("RepositoryOrdering", RepositoryOrdering)
ordering_direction = EnumType("OrderingDirection", OrderingDirection)

enum_types = [
    repository_ordering,
    ordering_direction,
]
