import logging
from datetime import datetime, timedelta
from typing import List, Mapping, Optional

import shared.rate_limits as rate_limits
import yaml
from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from django.conf import settings
from django.forms.utils import from_current_timezone
from graphql.type.definition import GraphQLResolveInfo
from shared.yaml import UserYaml

from codecov.db import sync_to_async
from codecov_auth.models import SERVICE_GITHUB, SERVICE_GITHUB_ENTERPRISE
from core.models import Branch, Repository
from graphql_api.actions.commits import repo_commits
from graphql_api.actions.components import (
    component_measurements,
    component_measurements_last_uploaded,
)
from graphql_api.actions.flags import flag_measurements, flags_for_repo
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import (
    queryset_to_connection,
    queryset_to_connection_sync,
)
from graphql_api.helpers.lookahead import lookahead
from graphql_api.types.coverage_analytics.coverage_analytics import (
    CoverageAnalyticsProps,
)
from graphql_api.types.enums import OrderingDirection, TestResultsFilterParameter
from graphql_api.types.enums.enum_types import MeasurementInterval
from graphql_api.types.errors.errors import NotFoundError, OwnerNotActivatedError
from services.components import ComponentMeasurements
from services.profiling import CriticalFile, ProfilingSummary
from services.redis_configuration import get_redis_connection
from timeseries.models import Dataset, Interval, MeasurementName
from utils.test_results import (
    GENERATE_TEST_RESULT_PARAM,
    generate_test_results,
)

log = logging.getLogger(__name__)

repository_bindable = ObjectType("Repository")

repository_bindable.set_alias("updatedAt", "updatestamp")

# latest_commit_at and coverage have their NULL value defaulted to -1/an old date
# so the NULL would end up last in the queryset as we do not have control over
# the order_by call. The true value of is under true_*; which would actually contain NULL
# see with_cache_latest_commit_at() from core/managers.py
repository_bindable.set_alias("latestCommitAt", "true_latest_commit_at")


@repository_bindable.field("oldestCommitAt")
def resolve_oldest_commit_at(
    repository: Repository, info: GraphQLResolveInfo
) -> Optional[datetime]:
    if hasattr(repository, "oldest_commit_at"):
        return repository.oldest_commit_at
    else:
        return None


@repository_bindable.field("branch")
def resolve_branch(
    repository: Repository, info: GraphQLResolveInfo, name: str
) -> Branch:
    command = info.context["executor"].get_command("branch")
    return command.fetch_branch(repository, name)


@repository_bindable.field("author")
def resolve_author(repository: Repository, info: GraphQLResolveInfo):
    return OwnerLoader.loader(info).load(repository.author_id)


@repository_bindable.field("commit")
def resolve_commit(repository: Repository, info: GraphQLResolveInfo, id):
    loader = CommitLoader.loader(info, repository.pk)
    return loader.load(id)


@repository_bindable.field("uploadToken")
def resolve_upload_token(repository: Repository, info: GraphQLResolveInfo):
    command = info.context["executor"].get_command("repository")
    return command.get_upload_token(repository)


@repository_bindable.field("pull")
def resolve_pull(repository: Repository, info: GraphQLResolveInfo, id):
    command = info.context["executor"].get_command("pull")
    return command.fetch_pull_request(repository, id)


@repository_bindable.field("pulls")
@convert_kwargs_to_snake_case
async def resolve_pulls(
    repository: Repository,
    info: GraphQLResolveInfo,
    filters=None,
    ordering_direction=OrderingDirection.DESC,
    **kwargs,
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
async def resolve_commits(
    repository: Repository, info: GraphQLResolveInfo, filters=None, **kwargs
):
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
async def resolve_branches(
    repository: Repository, info: GraphQLResolveInfo, filters=None, **kwargs
):
    command = info.context["executor"].get_command("branch")
    queryset = await command.fetch_branches(repository, filters)
    return await queryset_to_connection(
        queryset,
        ordering=("updatestamp",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@repository_bindable.field("defaultBranch")
def resolve_default_branch(repository: Repository, info: GraphQLResolveInfo):
    return repository.branch


@repository_bindable.field("profilingToken")
def resolve_profiling_token(repository: Repository, info: GraphQLResolveInfo):
    command = info.context["executor"].get_command("repository")
    return command.get_repository_token(repository, token_type="profiling")


@repository_bindable.field("staticAnalysisToken")
def resolve_static_analysis_token(repository: Repository, info: GraphQLResolveInfo):
    command = info.context["executor"].get_command("repository")
    return command.get_repository_token(repository, token_type="static_analysis")


@repository_bindable.field("criticalFiles")
@sync_to_async
def resolve_critical_files(
    repository: Repository, info: GraphQLResolveInfo
) -> List[CriticalFile]:
    """
    The current critical files for this repository - not tied to any
    particular commit or branch.  Based on the most recently received
    profiling data.

    See the `commit.criticalFiles` resolver for commit-specific files.
    """
    profiling_summary = ProfilingSummary(repository)
    return profiling_summary.critical_files


@repository_bindable.field("graphToken")
def resolve_graph_token(repository: Repository, info: GraphQLResolveInfo):
    return repository.image_token


@repository_bindable.field("yaml")
def resolve_repo_yaml(repository: Repository, info: GraphQLResolveInfo):
    if repository.yaml is None:
        return None
    return yaml.dump(repository.yaml)


@repository_bindable.field("bot")
@sync_to_async
def resolve_repo_bot(repository: Repository, info: GraphQLResolveInfo):
    return repository.bot


@repository_bindable.field("flags")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_flags(
    repository: Repository,
    info: GraphQLResolveInfo,
    filters: Mapping = None,
    ordering_direction: OrderingDirection = OrderingDirection.ASC,
    **kwargs,
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
def resolve_active(repository: Repository, info: GraphQLResolveInfo) -> bool:
    return repository.active or False


@repository_bindable.field("flagsCount")
@sync_to_async
def resolve_flags_count(repository: Repository, info: GraphQLResolveInfo) -> int:
    return repository.flags.filter(deleted__isnot=True).count()


@repository_bindable.field("flagsMeasurementsActive")
@sync_to_async
def resolve_flags_measurements_active(
    repository: Repository, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=repository.pk,
    ).exists()


@repository_bindable.field("flagsMeasurementsBackfilled")
@sync_to_async
def resolve_flags_measurements_backfilled(
    repository: Repository, info: GraphQLResolveInfo
) -> bool:
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
def resolve_components_measurements_active(
    repository: Repository, info: GraphQLResolveInfo
) -> bool:
    if not settings.TIMESERIES_ENABLED:
        return False

    return Dataset.objects.filter(
        name=MeasurementName.COMPONENT_COVERAGE.value,
        repository_id=repository.pk,
    ).exists()


@repository_bindable.field("componentsMeasurementsBackfilled")
@sync_to_async
def resolve_components_measurements_backfilled(
    repository: Repository, info: GraphQLResolveInfo
) -> bool:
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
def resolve_components_count(repository: Repository, info: GraphQLResolveInfo) -> int:
    repo_yaml_components = UserYaml.get_final_yaml(
        owner_yaml=repository.author.yaml,
        repo_yaml=repository.yaml,
        ownerid=repository.author.ownerid,
    ).get_components()

    return len(repo_yaml_components)


@repository_bindable.field("isATSConfigured")
def resolve_is_ats_configured(repository: Repository, info: GraphQLResolveInfo) -> bool:
    if not repository.yaml or "flag_management" not in repository.yaml:
        return False

    # See https://docs.codecov.com/docs/getting-started-with-ats-github-actions on configuring
    # flags. To use Automated Test Selection, a flag is required with Carryforward mode "labels".
    individual_flags = repository.yaml["flag_management"].get("individual_flags", {})
    return individual_flags.get("carryforward_mode") == "labels"


@repository_bindable.field("repositoryConfig")
def resolve_repository_config(repository: Repository, info: GraphQLResolveInfo):
    return repository


@repository_bindable.field("primaryLanguage")
def resolve_language(repository: Repository, info: GraphQLResolveInfo) -> str:
    return repository.language


@repository_bindable.field("languages")
def resolve_languages(repository: Repository, info: GraphQLResolveInfo) -> List[str]:
    return repository.languages


@repository_bindable.field("bundleAnalysisEnabled")
def resolve_bundle_analysis_enabled(
    repository: Repository, info: GraphQLResolveInfo
) -> Optional[bool]:
    return repository.bundle_analysis_enabled


@repository_bindable.field("testAnalyticsEnabled")
def resolve_test_analytics_enabled(
    repository: Repository, info: GraphQLResolveInfo
) -> Optional[bool]:
    return repository.test_analytics_enabled


@repository_bindable.field("coverageEnabled")
def resolve_coverage_enabled(
    repository: Repository, info: GraphQLResolveInfo
) -> Optional[bool]:
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
    info: GraphQLResolveInfo,
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
        components = [c for c in components if c.component_id in filters["components"]]

    component_ids = [c.component_id for c in components]
    all_measurements = component_measurements(
        repository, component_ids, interval, after, before, branch
    )

    last_measurements = component_measurements_last_uploaded(
        owner_id=repository.author.ownerid,
        repo_id=repository.repoid,
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


@repository_bindable.field("componentsYaml")
@convert_kwargs_to_snake_case
def resolve_component_yaml(
    repository: Repository, info: GraphQLResolveInfo, term_id: Optional[str]
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


@repository_bindable.field("isFirstPullRequest")
@sync_to_async
def resolve_is_first_pull_request(repository: Repository, info) -> bool:
    has_one_pr = repository.pull_requests.count() == 1

    if has_one_pr:
        first_pr = repository.pull_requests.first()
        return not first_pr.compared_to

    return False


@repository_bindable.field("isGithubRateLimited")
@sync_to_async
def resolve_is_github_rate_limited(repository: Repository, info) -> bool | None:
    if (
        repository.service != SERVICE_GITHUB
        and repository.service != SERVICE_GITHUB_ENTERPRISE
    ):
        return False
    repo_owner = repository.author
    try:
        redis_connection = get_redis_connection()
        rate_limit_redis_key = rate_limits.determine_entity_redis_key(
            owner=repo_owner, repository=repository
        )
        return rate_limits.determine_if_entity_is_rate_limited(
            redis_connection, rate_limit_redis_key
        )
    except Exception:
        log.warning(
            "Error when checking rate limit",
            extra=dict(repo_id=repository.repoid, has_owner=bool(repo_owner)),
        )
        return None


# TODO - remove with #2291
def convert_history_to_timedelta(interval: MeasurementInterval | None) -> timedelta:
    if interval is None:
        return timedelta(days=30)

    match interval:
        case MeasurementInterval.INTERVAL_1_DAY:
            return timedelta(days=1)
        case MeasurementInterval.INTERVAL_7_DAY:
            return timedelta(days=7)
        case MeasurementInterval.INTERVAL_30_DAY:
            return timedelta(days=30)


# TODO - remove with #2291
def convert_test_results_filter_parameter(
    parameter: TestResultsFilterParameter | None,
) -> GENERATE_TEST_RESULT_PARAM | None:
    if parameter is None:
        return None

    match parameter:
        case TestResultsFilterParameter.FLAKY_TESTS:
            return GENERATE_TEST_RESULT_PARAM.FLAKY
        case TestResultsFilterParameter.FAILED_TESTS:
            return GENERATE_TEST_RESULT_PARAM.FAILED
        case TestResultsFilterParameter.SLOWEST_TESTS:
            return GENERATE_TEST_RESULT_PARAM.SLOWEST
        case TestResultsFilterParameter.SKIPPED_TESTS:
            return GENERATE_TEST_RESULT_PARAM.SKIPPED


# TODO - remove with #2291
@repository_bindable.field("testResults")
async def resolve_test_results(
    repository: Repository,
    info: GraphQLResolveInfo,
    ordering=None,
    filters=None,
    **kwargs,
):
    parameter = (
        convert_test_results_filter_parameter(filters.get("parameter"))
        if filters
        else None
    )
    history = (
        convert_history_to_timedelta(filters.get("history"))
        if filters
        else timedelta(days=30)
    )

    queryset = await sync_to_async(generate_test_results)(
        repoid=repository.repoid,
        history=history,
        branch=filters.get("branch") if filters else None,
        parameter=parameter,
        testsuites=filters.get("test_suites") if filters else None,
        flags=filters.get("flags") if filters else None,
    )

    return await queryset_to_connection(
        queryset,
        ordering=(
            (ordering.get("parameter"), "name")
            if ordering
            else ("avg_duration", "name")
        ),
        ordering_direction=(
            ordering.get("direction") if ordering else OrderingDirection.DESC
        ),
        **kwargs,
    )


@repository_bindable.field("coverageAnalytics")
def resolve_coverage_analytics(
    repository: Repository,
    info: GraphQLResolveInfo,
) -> CoverageAnalyticsProps:
    return CoverageAnalyticsProps(
        repository=repository,
    )


@repository_bindable.field("testAnalytics")
def resolve_test_analytics(
    repository: Repository,
    info: GraphQLResolveInfo,
) -> Repository:
    """
    resolve_test_analytics defines the data that will get passed to the testAnalytics resolvers
    """
    return repository
