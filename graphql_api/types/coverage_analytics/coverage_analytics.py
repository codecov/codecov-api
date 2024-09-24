import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional, Union

from ariadne import ObjectType, UnionType
from graphql.type.definition import GraphQLResolveInfo

import timeseries.helpers as timeseries_helpers
from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.types.errors.errors import NotFoundError
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval, MeasurementSummary

log = logging.getLogger(__name__)

# Bindings for GraphQL types
coverage_analytics_bindable: ObjectType = ObjectType("CoverageAnalytics")
coverage_analytics_result_bindable: UnionType = UnionType("CoverageAnalyticsResult")


# CoverageAnalyticsProps is information passed from parent resolver (repository)
# to the coverage analytics resolver
@dataclass
class CoverageAnalyticsProps:
    repository: Repository


@coverage_analytics_result_bindable.type_resolver
def resolve_coverage_analytics_result_type(
    obj: Union[CoverageAnalyticsProps, NotFoundError], *_: Any
) -> Optional[str]:
    if isinstance(obj, CoverageAnalyticsProps):
        return "CoverageAnalyticsProps"
    elif isinstance(obj, NotFoundError):
        return "NotFoundError"
    return None


@coverage_analytics_bindable.field("percentCovered")
def resolve_percent_covered(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> Optional[float]:
    return parent.repository.recent_coverage if parent else None


@coverage_analytics_bindable.field("commitSha")
def resolve_commit_sha(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> Optional[str]:
    return parent.repository.coverage_sha if parent else None


@coverage_analytics_bindable.field("hits")
def resolve_hits(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> Optional[int]:
    return parent.repository.hits if parent else None


@coverage_analytics_bindable.field("misses")
def resolve_misses(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> Optional[int]:
    return parent.repository.misses if parent else None


@coverage_analytics_bindable.field("lines")
def resolve_lines(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> Optional[int]:
    return parent.repository.lines if parent else None


@coverage_analytics_bindable.field("measurements")
async def resolve_measurements(
    parent: CoverageAnalyticsProps,
    info: GraphQLResolveInfo,
    interval: Interval,
    before: Optional[datetime] = None,
    after: Optional[datetime] = None,
    branch: Optional[str] = None,
) -> Iterable[MeasurementSummary]:
    coverage_data = await sync_to_async(
        timeseries_helpers.repository_coverage_measurements_with_fallback
    )(
        parent.repository,
        interval,
        start_date=after,
        end_date=before,
        branch=branch,
    )

    measurements = await sync_to_async(fill_sparse_measurements)(
        coverage_data,
        interval,
        start_date=after,
        end_date=before,
    )

    return measurements
