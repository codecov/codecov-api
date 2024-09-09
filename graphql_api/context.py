from typing import Generic, TypeVar

from graphql.type.definition import GraphQLResolveInfo

T = TypeVar("T")


class TypedResolverInfo(GraphQLResolveInfo, Generic[T]):
    """
    TypedResolverInfo adds type safety to the `context` field of Ariadne's
    GraphQLResolveInfo by letting us declare the expected structure.

    Example usage:

    class CoverageAnalyticsContext(Protocol):
        repository: Optional[Repository]

    def resolve_percent_covered(
        coverage_analytics: CoverageAnalytics, info: TypedResolverInfo[CoverageAnalyticsContext]
    ) -> Optional[float]:
        repository = info.context.repository     # we are able to use IDE autocomplete here
        return repository.recent_coverage if repository else None
    """
    context: T
