from typing import Mapping

from ariadne import ObjectType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async
from django.conf import settings

from core.models import Branch
from graphql_api.actions.flags import flags_for_repo
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.helpers.connection import queryset_to_connection_sync
from graphql_api.helpers.lookahead import lookahead
from graphql_api.types.enums import OrderingDirection
from reports.models import RepositoryFlag
from timeseries.models import Interval, MeasurementSummary

branch_bindable = ObjectType("Branch")


@branch_bindable.field("head")
def resolve_head_commit(branch, info):
    if branch.head:
        loader = CommitLoader.loader(info, branch.repository_id)
        return loader.load(branch.head)


@branch_bindable.field("flags")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_flags(
    branch: Branch,
    info,
    filters: Mapping = None,
    ordering_direction: OrderingDirection = OrderingDirection.ASC,
    **kwargs
):
    repository = branch.repository

    queryset = flags_for_repo(repository, filters)
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
            interval = Interval[node.args["interval"]]
            flag_ids = [edge["node"].pk for edge in connection.edges]

            measurements = MeasurementSummary.agg_by(interval).filter(
                # TODO: use MeasurementName enum from other branch
                name="flag_coverage",
                owner_id=repository.author_id,
                repo_id=repository.pk,
                branch=branch.name,
                flag_id__in=flag_ids,
                timestamp_bin__gte=node.args["after"],
                timestamp_bin__lte=node.args["before"],
            )

            # force eager execution of query while we're in a sync context
            # (and store for child resolvers)
            info.context["measurements"] = list(measurements)
        else:
            info.context["measurements"] = []

    return connection
