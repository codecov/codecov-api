import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Mapping, Optional, Union

import sentry_sdk
from ariadne import ObjectType, UnionType
from django.conf import settings
from django.forms.utils import from_current_timezone
from graphql.type.definition import GraphQLResolveInfo
from shared.yaml import UserYaml

import timeseries.helpers as timeseries_helpers
from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.actions.components import (
    component_measurements,
    component_measurements_last_uploaded,
)
from graphql_api.actions.flags import flag_measurements, flags_for_repo
from graphql_api.helpers.connection import (
    queryset_to_connection_sync,
)
from graphql_api.helpers.lookahead import lookahead
from graphql_api.types.enums import OrderingDirection
from graphql_api.types.errors.errors import NotFoundError
from services.components import ComponentMeasurements
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Dataset, Interval, MeasurementName, MeasurementSummary

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


@sentry_sdk.trace
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


@sentry_sdk.trace
@coverage_analytics_bindable.field("components")
@sync_to_async
def resolve_components_measurements(
    parent: CoverageAnalyticsProps,
    info: GraphQLResolveInfo,
    interval: Interval,
    before: datetime,
    after: datetime,
    branch: Optional[str] = None,
    filters: Optional[Mapping] = None,
    ordering_direction: Optional[OrderingDirection] = OrderingDirection.ASC,
):
    components = UserYaml.get_final_yaml(
        owner_yaml=parent.repository.author.yaml,
        repo_yaml=parent.repository.yaml,
        ownerid=parent.repository.author.ownerid,
    ).get_components()

    if not settings.TIMESERIES_ENABLED or not components:
        return []

    if filters and "components" in filters:
        components = [c for c in components if c.component_id in filters["components"]]

    component_ids = [c.component_id for c in components]
    all_measurements = component_measurements(
        parent.repository, component_ids, interval, after, before, branch
    )

    last_measurements = component_measurements_last_uploaded(
        owner_id=parent.repository.author.ownerid,
        repo_id=parent.repository.repoid,
        measurable_ids=component_ids,
        branch=branch,
    )
    last_measurements_mapping = {
        row["measurable_id"]: row["last_uploaded"] for row in last_measurements
    }

    components_mapping = {
        component.component_id: component.name for component in components
    }

    queried_measurements = [
        ComponentMeasurements(
            raw_measurements=all_measurements.get(component_id, []),
            component_id=component_id,
            interval=interval,
            after=after,
            before=before,
            last_measurement=last_measurements_mapping.get(component_id),
            components_mapping=components_mapping,
        )
        for component_id in component_ids
    ]

    return sorted(
        queried_measurements,
        key=lambda c: c.name,
        reverse=ordering_direction == OrderingDirection.DESC,
    )


@coverage_analytics_bindable.field("componentsYaml")
def resolve_components_yaml(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo, term_id: Optional[str]
) -> List[str]:
    components = UserYaml.get_final_yaml(
        owner_yaml=parent.repository.author.yaml,
        repo_yaml=parent.repository.yaml,
        ownerid=parent.repository.author.ownerid,
    ).get_components()

    components = [
        {
            "id": c.component_id,
            "name": c.name,
        }
        for c in components
    ]

    if term_id:
        components = filter(lambda c: term_id in c["id"], components)

    return components


@coverage_analytics_bindable.field("componentsMeasurementsActive")
@sync_to_async
def resolve_components_measurements_active(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.COMPONENT_COVERAGE.value,
        repository_id=parent.repository.pk,
    ).exists()


@coverage_analytics_bindable.field("componentsMeasurementsBackfilled")
@sync_to_async
def resolve_components_measurements_backfilled(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    dataset = Dataset.objects.filter(
        name=MeasurementName.COMPONENT_COVERAGE.value,
        repository_id=parent.repository.pk,
    ).first()

    if not dataset:
        return False

    return dataset.is_backfilled()


@coverage_analytics_bindable.field("componentsCount")
@sync_to_async
def resolve_components_count(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> int:
    repo_yaml_components = UserYaml.get_final_yaml(
        owner_yaml=parent.repository.author.yaml,
        repo_yaml=parent.repository.yaml,
        ownerid=parent.repository.author.ownerid,
    ).get_components()

    return len(repo_yaml_components)


@sentry_sdk.trace
@coverage_analytics_bindable.field("flags")
@sync_to_async
def resolve_flags(
    parent: CoverageAnalyticsProps,
    info: GraphQLResolveInfo,
    filters: Mapping = None,
    ordering_direction: OrderingDirection = OrderingDirection.ASC,
    **kwargs,
):
    queryset = flags_for_repo(parent.repository, filters)
    connection = queryset_to_connection_sync(
        queryset,
        ordering=("flag_name",),
        ordering_direction=ordering_direction,
        **kwargs,
    )

    # We fetch the measurements in this resolver since there are multiple child
    # flag resolvers that depend on this data.  Additionally, we're able to fetch
    # measurements for all the flags being returned at once.
    # Use the lookahead to make sure we don't overfetch measurements that we don't
    # need.
    node = lookahead(info, ("edges", "node", "measurements"))
    if node:
        if settings.TIMESERIES_ENABLED:
            # TODO: is there a way to have these automatically casted at a
            # lower level (i.e. based on the schema)?
            interval = node.args["interval"]
            if isinstance(interval, str):
                interval = Interval[interval]
            after = node.args["after"]
            if isinstance(after, str):
                after = from_current_timezone(datetime.fromisoformat(after))
            before = node.args["before"]
            if isinstance(before, str):
                before = from_current_timezone(datetime.fromisoformat(before))

            flag_ids = [edge["node"].pk for edge in connection.edges]

            info.context["flag_measurements"] = flag_measurements(
                parent.repository, flag_ids, interval, after, before
            )
        else:
            info.context["flag_measurements"] = {}

    return connection


@coverage_analytics_bindable.field("flagsCount")
@sync_to_async
def resolve_flags_count(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> int:
    return parent.repository.flags.filter(deleted__isnot=True).count()


@coverage_analytics_bindable.field("flagsMeasurementsActive")
@sync_to_async
def resolve_flags_measurements_active(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=parent.repository.pk,
    ).exists()


@coverage_analytics_bindable.field("flagsMeasurementsBackfilled")
@sync_to_async
def resolve_flags_measurements_backfilled(
    parent: CoverageAnalyticsProps, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    dataset = Dataset.objects.filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=parent.repository.pk,
    ).first()

    if not dataset:
        return False

    return dataset.is_backfilled()
