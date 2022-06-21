from ariadne import ObjectType
from asgiref.sync import sync_to_async

from core.models import Branch
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
@sync_to_async
def resolve_flags(branch: Branch, info, **kwargs):
    info.context["branch"] = branch
    queryset = RepositoryFlag.objects.filter(
        repository=branch.repository,
        # TODO: this should ultimately be filtered by branch as well
    )

    results = queryset_to_connection_sync(
        queryset,
        ordering=("flag_name",),
        ordering_direction=OrderingDirection.ASC,
        **kwargs,
    )

    # We fetch the measurements in this resolver since there are multiple child
    # flag resolvers that depend on this data.  Additionally, we're able to fetch
    # measurements for all the flags being returned at once.
    # Use the lookahead to make sure we don't overfetch measurements that we don't
    # need.
    node = lookahead(info, ("edges", "node", "measurements"))
    if node:
        interval = Interval[node.args["interval"]]
        flag_ids = [edge["node"].pk for edge in results.edges]

        measurements = MeasurementSummary.agg_by(interval).filter(
            name="flag_coverage",
            repo_id=branch.repository_id,
            branch=branch.name,
            flag_id__in=flag_ids,
            timestamp_bin__gte=node.args["after"],
            timestamp_bin__lte=node.args["before"],
        )

        # force eager execution of query while we're in a sync context
        # (and store for child resolvers)
        info.context["measurements"] = list(measurements)

    return results
