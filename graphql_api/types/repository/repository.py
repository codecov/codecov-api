from datetime import datetime, timedelta
from typing import Iterable, List, Mapping, Optional

import yaml
from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from django.conf import settings
from django.forms.utils import from_current_timezone
from shared.yaml import UserYaml

import timeseries.helpers as timeseries_helpers
from codecov.db import sync_to_async
from core.models import Branch, Repository
from graphql_api.actions.commits import repo_commits
from graphql_api.actions.components import component_measurements
from graphql_api.actions.flags import flag_measurements, flags_for_repo
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import (
    queryset_to_connection,
    queryset_to_connection_sync,
)
from graphql_api.helpers.lookahead import lookahead
from graphql_api.types.enums import OrderingDirection
from graphql_api.types.errors.errors import NotFoundError, OwnerNotActivatedError
from services.components import ComponentMeasurements
from services.profiling import CriticalFile, ProfilingSummary
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Dataset, Interval, MeasurementName, MeasurementSummary

repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")

# latest_commit_at and coverage have their NULL value defaulted to -1/an old date
# so the NULL would end up last in the queryset as we do not have control over
# the order_by call. The true value of is under true_*; which would actually contain NULL
# see with_cache_latest_commit_at() from core/managers.py
repository_bindable.set_alias("latestCommitAt", "true_latest_commit_at")


@repository_bindable.field("oldestCommitAt")
def resolve_oldest_commit_at(repository: Repository, info):
    if hasattr(repository, "oldest_commit_at"):
        return repository.oldest_commit_at
    else:
        return None


@repository_bindable.field("coverage")
def resolve_coverage(repository: Repository, info):
    return repository.recent_coverage


@repository_bindable.field("coverageSha")
def resolve_coverage_sha(repository: Repository, info):
    return repository.coverage_sha


@repository_bindable.field("hits")
def resolve_hits(repository: Repository, info) -> Optional[int]:
    return repository.hits


@repository_bindable.field("misses")
def resolve_misses(repository: Repository, info) -> Optional[int]:
    return repository.misses


@repository_bindable.field("lines")
def resolve_lines(repository: Repository, info) -> Optional[int]:
    return repository.lines


@repository_bindable.field("branch")
def resolve_branch(repository, info, name: str) -> Branch:
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
    queryset = await sync_to_async(repo_commits)(repository, filters)
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
async def resolve_branches(repository, info, filters=None, **kwargs):
    command = info.context["executor"].get_command("branch")
    queryset = await command.fetch_branches(repository, filters)
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
    return command.get_repository_token(repository, token_type="profiling")


@repository_bindable.field("staticAnalysisToken")
def resolve_static_analysis_token(repository, info):
    command = info.context["executor"].get_command("repository")
    return command.get_repository_token(repository, token_type="static_analysis")


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
                repository, flag_ids, interval, after, before
            )
        else:
            info.context["flag_measurements"] = {}

    return connection


@repository_bindable.field("active")
def resolve_active(repository: Repository, info) -> bool:
    return repository.active or False


@repository_bindable.field("flagsCount")
@sync_to_async
def resolve_flags_count(repository: Repository, info) -> int:
    return repository.flags.filter(deleted__isnot=True).count()


@repository_bindable.field("flagsMeasurementsActive")
@sync_to_async
def resolve_flags_measurements_active(repository: Repository, info) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=repository.pk,
    ).exists()


@repository_bindable.field("flagsMeasurementsBackfilled")
@sync_to_async
def resolve_flags_measurements_backfilled(repository: Repository, info) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    dataset = Dataset.objects.filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=repository.pk,
    ).first()

    if not dataset:
        return False

    return dataset.is_backfilled()


@repository_bindable.field("componentsMeasurementsActive")
@sync_to_async
def resolve_components_measurements_active(repository: Repository, info) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.COMPONENT_COVERAGE.value,
        repository_id=repository.pk,
    ).exists()


@repository_bindable.field("componentsMeasurementsBackfilled")
@sync_to_async
def resolve_components_measurements_backfilled(repository: Repository, info) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    dataset = Dataset.objects.filter(
        name=MeasurementName.COMPONENT_COVERAGE.value,
        repository_id=repository.pk,
    ).first()

    if not dataset:
        return False

    return dataset.is_backfilled()


@repository_bindable.field("componentsCount")
@sync_to_async
def resolve_components_count(repository: Repository, info) -> int:
    repo_yaml_components = UserYaml.get_final_yaml(
        owner_yaml=repository.author.yaml,
        repo_yaml=repository.yaml,
        ownerid=repository.author.ownerid,
    ).get_components()

    return len(repo_yaml_components)


@repository_bindable.field("isATSConfigured")
def resolve_is_ats_configured(repository: Repository, info) -> bool:
    if not repository.yaml or "flag_management" not in repository.yaml:
        return False

    # See https://docs.codecov.com/docs/getting-started-with-ats-github-actions on configuring
    # flags. To use Automated Test Selection, a flag is required with Carryforward mode "labels".
    individual_flags = repository.yaml["flag_management"].get("individual_flags", {})
    return individual_flags.get("carryforward_mode") == "labels"


@repository_bindable.field("measurements")
@sync_to_async
def resolve_measurements(
    repository: Repository,
    info,
    interval: Interval,
    before: Optional[datetime] = None,
    after: Optional[datetime] = None,
    branch: Optional[str] = None,
) -> Iterable[MeasurementSummary]:
    return fill_sparse_measurements(
        timeseries_helpers.repository_coverage_measurements_with_fallback(
            repository,
            interval,
            start_date=after,
            end_date=before,
            branch=branch,
        ),
        interval,
        start_date=after,
        end_date=before,
    )


@repository_bindable.field("repositoryConfig")
def resolve_repository_config(repository: Repository, info):
    return repository


@repository_bindable.field("primaryLanguage")
def resolve_language(repository: Repository, info) -> str:
    return repository.language


@repository_bindable.field("languages")
def resolve_languages(repository: Repository, info) -> List[str]:
    return repository.languages


@repository_bindable.field("bundleAnalysisEnabled")
def resolve_bundle_analysis_enabled(repository: Repository, info) -> Optional[bool]:
    return repository.bundle_analysis_enabled


@repository_bindable.field("coverageEnabled")
def resolve_coverage_enabled(repository: Repository, info) -> Optional[bool]:
    return repository.coverage_enabled


repository_result_bindable = UnionType("RepositoryResult")


@repository_result_bindable.type_resolver
def resolve_repository_result_type(obj, *_):
    if isinstance(obj, Repository):
        return "Repository"
    elif isinstance(obj, OwnerNotActivatedError):
        return "OwnerNotActivatedError"
    elif isinstance(obj, NotFoundError):
        return "NotFoundError"


@repository_bindable.field("components")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_component_measurements(
    repository: Repository,
    info,
    interval: Interval,
    before: datetime,
    after: datetime,
    branch: Optional[str] = None,
    filters: Optional[Mapping] = None,
    ordering_direction: Optional[OrderingDirection] = OrderingDirection.ASC,
):
    components = UserYaml.get_final_yaml(
        owner_yaml=repository.author.yaml,
        repo_yaml=repository.yaml,
        ownerid=repository.author.ownerid,
    ).get_components()

    if not settings.TIMESERIES_ENABLED or not components:
        return []

    if filters and "components" in filters:
        components = [
            c_id for c_id in components if c_id.component_id in filters["components"]
        ]

    component_ids = [c.component_id for c in components]
    all_measurements = component_measurements(
        repository, component_ids, interval, after, before, branch
    )
    queried_measurements = [
        ComponentMeasurements(
            raw_measurements=all_measurements.get(component_id, []),
            component_id=component_id,
            interval=interval,
            after=after,
            before=before,
        )
        for component_id in component_ids
    ]

    return sorted(
        queried_measurements,
        key=lambda c: c.name,
        reverse=ordering_direction == OrderingDirection.DESC,
    )


@repository_bindable.field("componentsYaml")
@convert_kwargs_to_snake_case
def resolve_component_yaml(
    repository: Repository, info, term_id: Optional[str]
) -> List[str]:
    components = UserYaml.get_final_yaml(
        owner_yaml=repository.author.yaml,
        repo_yaml=repository.yaml,
        ownerid=repository.author.ownerid,
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
