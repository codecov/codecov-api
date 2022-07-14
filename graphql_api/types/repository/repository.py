from typing import List, Mapping

import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Avg, Max, Min

from core.models import Repository
from graphql_api.actions.flags import flags_for_repo
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import (
    queryset_to_connection,
    queryset_to_connection_sync,
)
from graphql_api.helpers.lookahead import lookahead
from graphql_api.types.enums import OrderingDirection
from services.profiling import CriticalFile, ProfilingSummary
from timeseries.models import Interval, MeasurementName, MeasurementSummary

repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")

# latest_commit_at and coverage have their NULL value defaulted to -1/an old date
# so the NULL would end up last in the queryset as we do not have control over
# the order_by call. The true value of is under true_*; which would actually contain NULL
# see with_cache_latest_commit_at() from core/managers.py
repository_bindable.set_alias("latestCommitAt", "true_latest_commit_at")


@repository_bindable.field("coverage")
def resolve_coverage(repository: Repository, info):
    return repository.recent_coverage


@repository_bindable.field("coverageSha")
def resolve_coverage_sha(repository: Repository, info):
    return repository.coverage_sha


@repository_bindable.field("branch")
def resolve_branch(repository, info, name):
    command = info.context["executor"].get_command("branch")
    return command.fetch_branch(repository, name)


@repository_bindable.field("author")
def resolve_author(repository, info):
    return OwnerLoader.loader(info).load(repository.author_id)


@repository_bindable.field("commit")
def resolve_commit(repository, info, id):
    loader = CommitLoader.loader(info, repository.pk)
    return loader.load(id)


@repository_bindable.field("uploadToken")
def resolve_upload_token(repository, info):
    command = info.context["executor"].get_command("repository")
    return command.get_upload_token(repository)


@repository_bindable.field("pull")
def resolve_pull(repository, info, id):
    command = info.context["executor"].get_command("pull")
    return command.fetch_pull_request(repository, id)


@repository_bindable.field("pulls")
@convert_kwargs_to_snake_case
async def resolve_pulls(
    repository, info, filters=None, ordering_direction=OrderingDirection.DESC, **kwargs
):
    command = info.context["executor"].get_command("pull")
    queryset = await command.fetch_pull_requests(repository, filters)
    return await queryset_to_connection(
        queryset,
        ordering=("pullid",),
        ordering_direction=ordering_direction,
        **kwargs,
    )


@repository_bindable.field("commits")
@convert_kwargs_to_snake_case
async def resolve_commits(repository, info, filters=None, **kwargs):
    command = info.context["executor"].get_command("commit")
    queryset = await command.fetch_commits(repository, filters)
    connection = await queryset_to_connection(
        queryset,
        ordering=("timestamp",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )

    for edge in connection.edges:
        commit = edge["node"]
        # cache all resulting commits in dataloader
        loader = CommitLoader.loader(info, repository.repoid)
        loader.cache(commit)

    return connection


@repository_bindable.field("branches")
@convert_kwargs_to_snake_case
async def resolve_branches(repository, info, **kwargs):
    command = info.context["executor"].get_command("branch")
    queryset = await command.fetch_branches(repository)
    return await queryset_to_connection(
        queryset,
        ordering=("updatestamp",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@repository_bindable.field("defaultBranch")
def resolve_default_branch(repository, info):
    return repository.branch


@repository_bindable.field("profilingToken")
def resolve_profiling_token(repository, info):
    command = info.context["executor"].get_command("repository")
    return command.get_profiling_token(repository)


@repository_bindable.field("criticalFiles")
@sync_to_async
def resolve_critical_files(repository: Repository, info) -> List[CriticalFile]:
    """
    The current critical files for this repository - not tied to any
    particular commit or branch.  Based on the most recently received
    profiling data.

    See the `commit.criticalFiles` resolver for commit-specific files.
    """
    profiling_summary = ProfilingSummary(repository)
    return profiling_summary.critical_files


@repository_bindable.field("graphToken")
def resolve_graph_token(repository, info):
    return repository.image_token


@repository_bindable.field("yaml")
def resolve_repo_yaml(repository, info):
    if repository.yaml is None:
        return None
    return yaml.dump(repository.yaml)


@repository_bindable.field("bot")
@sync_to_async
def resolve_repo_bot(repository, info):
    return repository.bot


@repository_bindable.field("flags")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_flags(
    repository: Repository,
    info,
    filters: Mapping = None,
    ordering_direction: OrderingDirection = OrderingDirection.ASC,
    **kwargs
):
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
            interval = node.args["interval"]
            if isinstance(interval, str):
                interval = Interval[interval]

            flag_ids = [edge["node"].pk for edge in connection.edges]

            measurements = (
                MeasurementSummary.agg_by(interval)
                .filter(
                    name=MeasurementName.FLAG_COVERAGE.value,
                    owner_id=repository.author_id,
                    repo_id=repository.pk,
                    flag_id__in=flag_ids,
                    timestamp_bin__gte=node.args["after"],
                    timestamp_bin__lte=node.args["before"],
                )
                .values("timestamp_bin", "owner_id", "repo_id", "flag_id")
                .annotate(
                    avg=Avg("value_avg"),
                    min=Min("value_min"),
                    max=Max("value_max"),
                )
                .order_by("timestamp_bin")
            )

            # force eager execution of query while we're in a sync context
            # (and store for child resolvers)
            info.context["measurements"] = list(measurements)
        else:
            info.context["measurements"] = []

    return connection
